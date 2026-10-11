"""Bridge a Wintun IPv4 adapter to reliable acoustic AX.25 PID CC over USB CDC."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
import queue
import re
import struct
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0,CFG["python_libraries"])
import serial
from usb_chat_web import HTML, handler_for

USB_RX=re.compile(rb"^USB_RX SRC=(\S+) DEST=(\S+) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]*)$")
GROUP_RX=re.compile(rb"^USB_GROUP_RX SRC=([A-Z0-9]{1,6}) ID=(\d+) HEX=([0-9A-Fa-f]+)$")
ERROR_NO_MORE_ITEMS=259


def elevated():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def paced_write(port,data):
    for offset in range(0,len(data),32):
        port.write(data[offset:offset+32]);port.flush();time.sleep(.01)


def event_time():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def capture_usb_snapshot(port_name,phase):
    script=ROOT/"USB_EVENT_SNAPSHOT.ps1"
    if not script.exists():return
    def run_snapshot():
        try:
            result=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass",
                                   "-File",str(script),"-Port",port_name,"-Phase",phase],
                                  capture_output=True,text=True,timeout=20,
                                  creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if result.returncode:print(f"USB SNAPSHOT FAILED ({phase}): {result.stderr[-300:]}",flush=True)
        except (OSError,subprocess.TimeoutExpired) as error:
            print(f"USB SNAPSHOT FAILED ({phase}): {error}",flush=True)
    threading.Thread(target=run_snapshot,name=f"usb-snapshot-{phase}",daemon=True).start()


class Wintun:
    def __init__(self,dll_path,name):
        self.dll=ctypes.WinDLL(str(dll_path),use_last_error=True)
        self.dll.WintunCreateAdapter.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_void_p];self.dll.WintunCreateAdapter.restype=ctypes.c_void_p
        self.dll.WintunCloseAdapter.argtypes=[ctypes.c_void_p]
        self.dll.WintunGetAdapterLUID.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        self.dll.WintunStartSession.argtypes=[ctypes.c_void_p,wintypes.DWORD];self.dll.WintunStartSession.restype=ctypes.c_void_p
        self.dll.WintunEndSession.argtypes=[ctypes.c_void_p]
        self.dll.WintunReceivePacket.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD)];self.dll.WintunReceivePacket.restype=ctypes.POINTER(ctypes.c_ubyte)
        self.dll.WintunReleaseReceivePacket.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ubyte)]
        self.dll.WintunAllocateSendPacket.argtypes=[ctypes.c_void_p,wintypes.DWORD];self.dll.WintunAllocateSendPacket.restype=ctypes.POINTER(ctypes.c_ubyte)
        self.dll.WintunSendPacket.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ubyte)]
        self.adapter=self.dll.WintunCreateAdapter(name,"AcousticAX25",None)
        if not self.adapter: raise ctypes.WinError(ctypes.get_last_error())
        luid=ctypes.c_uint64();self.dll.WintunGetAdapterLUID(self.adapter,ctypes.byref(luid))
        index=wintypes.ULONG();convert=ctypes.windll.iphlpapi.ConvertInterfaceLuidToIndex
        convert.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(wintypes.ULONG)]
        error=convert(ctypes.byref(luid),ctypes.byref(index))
        if error: raise OSError(error,"ConvertInterfaceLuidToIndex")
        self.index=index.value
        self.session=self.dll.WintunStartSession(self.adapter,0x400000)
        if not self.session: raise ctypes.WinError(ctypes.get_last_error())

    def receive(self):
        size=wintypes.DWORD();pointer=self.dll.WintunReceivePacket(self.session,ctypes.byref(size))
        if not pointer:
            error=ctypes.get_last_error()
            if error==ERROR_NO_MORE_ITEMS:return None
            raise ctypes.WinError(error)
        try:return ctypes.string_at(pointer,size.value)
        finally:self.dll.WintunReleaseReceivePacket(self.session,pointer)

    def inject(self,packet):
        pointer=self.dll.WintunAllocateSendPacket(self.session,len(packet))
        if not pointer:raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(pointer,packet,len(packet));self.dll.WintunSendPacket(self.session,pointer)

    def close(self):
        if getattr(self,"session",None):self.dll.WintunEndSession(self.session);self.session=None
        if getattr(self,"adapter",None):self.dll.WintunCloseAdapter(self.adapter);self.adapter=None


def configure(index,local_ip,remote_ip):
    script=(f"$ErrorActionPreference='Stop';"
            f"Get-NetIPAddress -InterfaceIndex {index} -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false;"
            f"New-NetIPAddress -InterfaceIndex {index} -IPAddress '{local_ip}' -PrefixLength 32 | Out-Null;"
            f"Set-NetIPInterface -InterfaceIndex {index} -AddressFamily IPv4 -NlMtuBytes 1500;"
            f"Get-NetRoute -InterfaceIndex {index} -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object DestinationPrefix -eq '{remote_ip}/32' | Remove-NetRoute -Confirm:$false;"
            f"New-NetRoute -InterfaceIndex {index} -DestinationPrefix '{remote_ip}/32' -NextHop '0.0.0.0' -RouteMetric 1 | Out-Null")
    subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",script],check=True)


def valid_ipv4(packet):
    return len(packet)>=20 and packet[0]>>4==4 and struct.unpack("!H",packet[2:4])[0]==len(packet) and len(packet)<=1500


def allowed_outbound(packet,remote_ip,udp_port,pass_all):
    if not valid_ipv4(packet) or packet[16:20]!=bytes(map(int,remote_ip.split("."))):return False
    if pass_all:return True
    ihl=(packet[0]&15)*4
    if len(packet)<ihl+8:return False
    if packet[9]==1:return packet[ihl] in (0,8)  # Echo Reply and Echo Request.
    if packet[9]==17:return struct.unpack("!H",packet[ihl+2:ihl+4])[0]==udp_port
    return False


def start_native_chat(chat,stop):
    def ui():
        import tkinter as tk
        from tkinter import ttk
        root=tk.Tk();root.title("ATOM Peer Chat");root.geometry("680x460")
        status=tk.StringVar(value=chat.status)
        ttk.Label(root,textvariable=status,padding=(10,8)).pack(fill="x")
        mode=tk.StringVar(value="直接")
        selector=ttk.Combobox(root,textvariable=mode,values=("直接","グループ CHAT"),state="readonly",width=18)
        selector.pack(anchor="w",padx=10)
        def change_mode(_event=None):
            try:chat.set_mode("group" if mode.get()=="グループ CHAT" else "direct")
            except Exception as error:status.set(f"切り替え失敗: {error}")
        selector.bind("<<ComboboxSelected>>",change_mode)
        bar=ttk.Frame(root,padding=10);bar.pack(fill="x")
        ttk.Label(bar,text="送信文:").pack(side="left",padx=(0,8))
        message=ttk.Entry(bar,font=("Yu Gothic UI",12));message.pack(side="left",fill="x",expand=True)
        sent_id=0
        def send(_event=None):
            text=message.get()
            if not text:return "break"
            try:chat.send(text);message.delete(0,"end")
            except Exception as error:status.set(f"送信失敗: {error}")
            return "break"
        ttk.Button(bar,text="送信",command=send).pack(side="left",padx=(8,0));message.bind("<Return>",send)
        log=tk.Text(root,state="disabled",wrap="word",font=("Yu Gothic UI",12))
        log.pack(fill="both",expand=True,padx=10,pady=(0,10))
        def poll():
            nonlocal sent_id
            if stop.is_set():
                root.destroy();return
            status.set(chat.status)
            with chat.lock:events=[item.copy() for item in chat.events if item["id"]>sent_id]
            if events:
                log.configure(state="normal")
                for item in events:
                    log.insert("end",f'{item["who"]}: {item["text"]}\n');sent_id=item["id"]
                log.see("end");log.configure(state="disabled")
            root.after(100,poll)
        root.protocol("WM_DELETE_WINDOW",stop.set)
        root.after(100,poll);message.focus_set();root.mainloop()
    ui()


def run(args):
    if not elevated():raise PermissionError("Run this bridge as Administrator so Wintun can create/configure the adapter")
    custom_dll=getattr(args,"wintun_dll","")
    dll=Path(custom_dll) if custom_dll else ROOT/"wintun"/"amd64"/"wintun.dll"
    tun=Wintun(dll,args.adapter);port=serial.Serial(args.port,115200,timeout=.02);port.reset_input_buffer();time.sleep(.4)
    configure(tun.index,args.local_ip,args.remote_ip)
    print(f"READY adapter={args.adapter} ifIndex={tun.index} {args.local_ip}/32 route={args.remote_ip}/32 port={args.port}",flush=True)
    stop=threading.Event();buffer=bytearray();outbound=queue.Queue(maxsize=args.queue_size);tx_complete=threading.Event();rx_ipv4=threading.Event();tx_result={"state":None}
    port_lock=threading.Lock();port_state={"port":port};connected=threading.Event();connected.set()
    def current_port():
        with port_lock:return port_state["port"]
    class Chat:
        def __init__(self):
            self.lock=threading.Lock();self.events=[];self.next_id=1;self.mode="direct";self.link_status="接続済み"
            self.chat_generation=0
            self.status=f"{args.port} / {self.link_status} / 直接"
        def add(self,who,text):
            with self.lock:
                self.events.append({"id":self.next_id,"who":who,"text":text});self.next_id+=1;self.events=self.events[-200:]
            if who in ("自分", "送達", "送信失敗・後続は未送信", "未送信"):
                print(f"CHAT EVENT at={event_time()} {who}: {text}",flush=True)
        def send(self,text):
            if not connected.is_set():raise RuntimeError("ATOM USB再接続中です。復帰後に再送してください")
            diagnostic=text.strip()
            if diagnostic in ("/rx-off", "/rx-on"):
                command=b"q" if diagnostic=="/rx-off" else b"l"
                try:outbound.put_nowait(("control",command))
                except queue.Full:raise RuntimeError("送信キューが満杯です")
                self.add("診断", "ATOMへ音響受信の"+("停止" if diagnostic=="/rx-off" else "再開")+"を指示しました")
                return
            payload=text.encode("utf-8")
            with self.lock:
                mode=self.mode
                limit=198 if mode=="group" else 1500
                if not 1<=len(payload)<=limit:raise ValueError(f"本文はUTF-8で1～{limit}バイトです")
                try:outbound.put_nowait(("group",payload) if mode=="group" else ("chat",(self.chat_generation,payload,text)))
                except queue.Full:raise RuntimeError("送信キューが満杯です")
            self.add("自分（グループ）" if mode=="group" else "自分",text)
        def set_mode(self,mode):
            if mode not in ("direct","group"):raise ValueError("mode must be direct or group")
            with self.lock:
                if connected.is_set():
                    try:outbound.put_nowait(("mode",None))
                    except queue.Full:raise RuntimeError("送信キューが満杯です")
                self.mode=mode;self._refresh_status()
        def set_link_status(self,status):
            with self.lock:self.link_status=status;self._refresh_status()
        def fail_direct(self,generation):
            with self.lock:
                if self.chat_generation==generation:self.chat_generation+=1
        def _refresh_status(self):
            self.status=f"{args.port} / {self.link_status} / {'グループ CHAT' if self.mode=='group' else '直接'}"
    chat=Chat();http=None
    outbound.put_nowait(("mode",None))
    def disconnect(error,observed_port=None):
        with port_lock:
            old=port_state["port"]
            if old is None or (observed_port is not None and old is not observed_port):return
            port_state["port"]=None;connected.clear();tx_complete.set()
        try:old.close()
        except (serial.SerialException,OSError):pass
        count("usb_disconnects")
        chat.fail_direct(chat.chat_generation)
        chat.set_link_status("USB再接続中")
        chat.add("システム",f"ATOM USB切断: {error}。COMポートの復帰を待っています")
        print(f"SERIAL DISCONNECTED at={event_time()}: {error}; reconnecting {args.port}",flush=True)
        capture_usb_snapshot(args.port,"disconnect")
    if args.chat_http_port>0:
        http=ThreadingHTTPServer((args.chat_listen,args.chat_http_port),handler_for(chat))
        threading.Thread(target=http.serve_forever,daemon=True).start()
        print(f"CHAT http://{args.chat_listen}:{args.chat_http_port}/",flush=True)
    stats={"captured":0,"filtered":0,"tx_started":0,"tx_sent":0,"tx_failed":0,"tx_busy":0,"retries":0,
           "usb_disconnects":0,"usb_reconnects":0,
           "rx_ipv4":0,"queue_drops":0,"queue_high_water":0};stats_lock=threading.Lock();started=time.monotonic()
    def count(name,amount=1):
        with stats_lock:stats[name]+=amount
    def print_stats():
        with stats_lock:snapshot=dict(stats)
        elapsed=max(.001,time.monotonic()-started)
        print("STATS "+" ".join(f"{key}={value}" for key,value in snapshot.items())+
              f" queue_now={outbound.qsize()} uptime_s={elapsed:.1f}",flush=True)
    def serial_to_tun():
        last_reconnect_error=0.0
        while not stop.is_set():
            active=current_port()
            if active is None:
                replacement=None
                try:
                    replacement=serial.Serial(args.port,115200,timeout=.02,write_timeout=2)
                    replacement.reset_input_buffer()
                    if stop.wait(.4):replacement.close();return
                    with chat.lock:mode=chat.mode
                    paced_write(replacement,f"group {'on' if mode=='group' else 'off'}\n".encode("ascii"))
                    with port_lock:
                        if port_state["port"] is None:
                            port_state["port"]=replacement;connected.set()
                            replacement=None
                    if replacement is not None:replacement.close()
                    else:
                        count("usb_reconnects")
                        buffer.clear();chat.set_link_status("接続済み")
                        chat.add("システム",f"ATOM USB再接続: {args.port}。通信を再開しました")
                        print(f"SERIAL RECONNECTED at={event_time()}: {args.port}",flush=True)
                        capture_usb_snapshot(args.port,"reconnect")
                    continue
                except (serial.SerialException,OSError) as error:
                    if replacement is not None:
                        try:replacement.close()
                        except (serial.SerialException,OSError):pass
                    if time.monotonic()-last_reconnect_error>=10:
                        print(f"SERIAL RECONNECT WAIT: {error}",flush=True)
                        last_reconnect_error=time.monotonic()
                    stop.wait(1)
                    continue
            try:data=active.read(max(1,active.in_waiting))
            except (serial.SerialException,OSError) as error:
                disconnect(error,active);continue
            if data:buffer.extend(data)
            if len(buffer)>65536:
                print(f"WARNING: discarded {len(buffer)} bytes of unterminated serial data",flush=True)
                buffer.clear()
            while b"\n" in buffer:
                line,_,rest=buffer.partition(b"\n");buffer[:]=rest;line=line.strip();match=USB_RX.match(line);group=GROUP_RX.match(line)
                try:
                    handle_serial_line(line,match,group)
                except Exception as error:
                    print(f"SERIAL RX ERROR: {error!r} line={line[:160]!r}",flush=True)
                    stop.set();return
    def handle_serial_line(line,match,group):
        if match:
            pid=match.group(3).upper();payload=bytes.fromhex(match.group(4).decode("ascii"))
            if pid==b"CC" and valid_ipv4(payload):tun.inject(payload);rx_ipv4.set();count("rx_ipv4");print(f"RX IPv4 {len(payload)} bytes -> Wintun",flush=True)
            elif pid==b"F0":
                text=payload.decode("utf-8",errors="replace");chat.add(f"{match.group(1).decode(errors='replace')}>{match.group(2).decode(errors='replace')}",text);print(f"RX CHAT {len(payload)} bytes",flush=True)
        elif group:
            text=bytes.fromhex(group.group(3).decode("ascii")).decode("utf-8",errors="replace")
            chat.add(f"{group.group(1).decode('ascii')}>CHAT（グループ）",text)
            print(f"RX GROUP CHAT {len(text.encode('utf-8'))} bytes",flush=True)
        elif line.startswith(b"RELIABLE RETRY"):count("retries")
        elif line.startswith(b"RELIABLE SENT"):
            count("tx_sent");tx_result["state"]="sent";tx_complete.set();print(f"SERIAL STATUS at={event_time()} {line.decode('ascii',errors='replace')}",flush=True)
        elif line.startswith(b"RELIABLE FAILED"):
            count("tx_failed");tx_result["state"]="failed";tx_complete.set();print(f"SERIAL STATUS at={event_time()} {line.decode('ascii',errors='replace')}",flush=True)
        elif line.startswith(b"RELIABLE BUSY"):
            count("tx_busy");tx_result["state"]="busy";tx_complete.set();print(f"SERIAL STATUS at={event_time()} {line.decode('ascii',errors='replace')}",flush=True)
        elif line.startswith(b"GROUP TX OK"):
            count("tx_sent");tx_result["state"]="sent";tx_complete.set();print("GROUP TX OK",flush=True)
        elif line.startswith(b"GROUP TX FAILED"):
            count("tx_failed");tx_result["state"]="failed";tx_complete.set();chat.add("システム",line.decode("utf-8",errors="replace"))
        elif line.startswith((b"LIVE RX stopped",b"STATE RX LISTEN")):
            chat.add("ATOM",line.decode("utf-8",errors="replace"))
            print(line.decode("utf-8",errors="replace"),flush=True)
        elif line.startswith(b"GROUP WIRE "):
            print(line.decode("utf-8",errors="replace"),flush=True)
        elif line.startswith((b"BOOT DIAG",b"NORMAL READY",b"Display ready",b"ESP-ROM",b"rst:",
                              b"Brownout",b"Guru Meditation",b"Rebooting")):
            print(f"SERIAL BOOT at={event_time()}: {line.decode('utf-8',errors='replace')}",flush=True)
    def tun_to_serial():
        while not stop.is_set():
            try:kind,payload=outbound.get(timeout=.1)
            except queue.Empty:continue
            if kind=="chat":
                generation,payload,chat_text=payload
                with chat.lock:stale=generation!=chat.chat_generation
                if stale:
                    chat.add("未送信",chat_text)
                    outbound.task_done();continue
            while not connected.wait(.1):
                if stop.is_set():outbound.task_done();return
            if kind=="chat":
                with chat.lock:stale=generation!=chat.chat_generation
                if stale:
                    chat.add("未送信",chat_text)
                    outbound.task_done();continue
            active=current_port()
            if active is None:
                outbound.task_done();continue
            if kind in ("control","mode"):
                if kind=="mode":
                    with chat.lock:mode=chat.mode
                    payload=f"group {'on' if mode=='group' else 'off'}\n".encode("ascii")
                try:paced_write(active,payload)
                except (serial.SerialException,OSError) as error:
                    disconnect(error,active)
                outbound.task_done();continue
            tx_result["state"]=None;tx_complete.clear();rx_ipv4.clear();count("tx_started")
            prefix="y" if kind=="ip" else "k" if kind=="group" else "z"
            try:paced_write(active,(prefix+" "+payload.hex()+"\n").encode("ascii"))
            except (serial.SerialException,OSError) as error:
                if kind=="chat":chat.fail_direct(generation);chat.add("送信失敗・後続は未送信",chat_text)
                count("tx_failed");disconnect(error,active);outbound.task_done();continue
            print(f"TX {'IPv4' if kind=='ip' else 'GROUP CHAT' if kind=='group' else 'CHAT'} {len(payload)} bytes -> acoustic",flush=True)
            completed=tx_complete.wait(40 if kind=="group" else 180)
            if current_port() is not active:
                count("tx_failed")
                message=f"TX interrupted by USB disconnect ({kind}, {len(payload)} bytes); retry after reconnect"
                print("WARNING: "+message,flush=True);chat.add("システム",message)
            elif not completed:
                count("tx_failed")
                message=f"TX completion timeout ({kind}, {len(payload)} bytes); ATOMの応答を確認してください"
                print("WARNING: "+message,flush=True);chat.add("システム",message)
            if kind=="chat":
                if completed and tx_result["state"]=="sent":chat.add("送達",chat_text)
                else:
                    chat.fail_direct(generation)
                    chat.add("送信失敗・後続は未送信",chat_text)
            elif kind=="ip" and args.turnaround>0 and not rx_ipv4.wait(args.turnaround):print(f"TURNAROUND {args.turnaround}s expired; sending next queued packet",flush=True)
            outbound.task_done()
    rx_thread=threading.Thread(target=serial_to_tun,daemon=True);tx_thread=threading.Thread(target=tun_to_serial,daemon=True)
    rx_thread.start();tx_thread.start()
    def tun_loop():
        try:
            while not stop.is_set():
                packet=tun.receive()
                if packet and allowed_outbound(packet,args.remote_ip,args.udp_port,args.pass_all):
                    count("captured")
                    if not connected.is_set():count("queue_drops")
                    else:
                        try:
                            outbound.put_nowait(("ip",packet))
                            with stats_lock:stats["queue_high_water"]=max(stats["queue_high_water"],outbound.qsize())
                        except queue.Full:count("queue_drops");print("DROP: outbound IPv4 queue full",flush=True)
                elif packet:count("filtered")
                else:time.sleep(.005)
                if args.stats_interval>0 and time.monotonic()-getattr(run,"last_stats",started)>=args.stats_interval:
                    run.last_stats=time.monotonic();print_stats()
        except Exception as error:
            print(f"WINTUN ERROR: {error!r}",flush=True);stop.set()
    try:
        if args.chat_native:
            threading.Thread(target=tun_loop,name="wintun-receive",daemon=True).start()
            print("CHAT native peer window",flush=True)
            start_native_chat(chat,stop)
        else:tun_loop()
    except KeyboardInterrupt:pass
    finally:
        stop.set()
        if http:http.shutdown();http.server_close()
        rx_thread.join(1);tx_thread.join(1)
        active=current_port()
        if active is not None:active.close()
        tun.close()


def main():
    parser=argparse.ArgumentParser(description="Wintun <-> reliable acoustic AX.25 IPv4 bridge")
    parser.add_argument("--port",default="COM5");parser.add_argument("--adapter",default="AcousticAX25")
    parser.add_argument("--local-ip",default="10.23.0.1");parser.add_argument("--remote-ip",default="10.23.0.2")
    parser.add_argument("--turnaround",type=float,default=10,help="wait for an inbound IPv4 packet before dequeuing the next packet")
    parser.add_argument("--queue-size",type=int,default=32,help="maximum queued outbound IPv4 packets")
    parser.add_argument("--stats-interval",type=float,default=30,help="periodic STATS output in seconds; 0 disables")
    parser.add_argument("--udp-port",type=int,default=7000,help="UDP destination port admitted to the acoustic queue")
    parser.add_argument("--pass-all",action="store_true",help="admit every IPv4 protocol for the remote IP")
    parser.add_argument("--chat-listen",default="127.0.0.1",help="browser chat bind address")
    parser.add_argument("--chat-http-port",type=int,default=0,help="enable browser chat on this HTTP port; 0 disables")
    parser.add_argument("--chat-native",action="store_true",help="open a native peer-to-peer chat window")
    parser.add_argument("--wintun-dll",default="",help="path to the separately installed Wintun DLL")
    args=parser.parse_args();run(args)


if __name__=="__main__":main()
