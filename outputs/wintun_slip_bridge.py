"""Bridge Windows Wintun IPv4 packets to USB CDC SLIP and acoustic AX.25."""
import argparse
import json
import queue
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0,CFG["python_libraries"])
import serial
from wintun_bridge import Wintun,allowed_outbound,configure,elevated,valid_ipv4

END=0xc0;ESC=0xdb;ESC_END=0xdc;ESC_ESC=0xdd


def slip_encode(data):
    out=bytearray([END])
    for c in data:
        if c==END:out.extend((ESC,ESC_END))
        elif c==ESC:out.extend((ESC,ESC_ESC))
        else:out.append(c)
    out.append(END);return bytes(out)


class SlipDecoder:
    def __init__(self):self.data=bytearray();self.escaped=False
    def feed(self,data):
        frames=[]
        for c in data:
            if c==END:
                if self.data:frames.append(bytes(self.data))
                self.data.clear();self.escaped=False;continue
            if self.escaped:
                if c==ESC_END:c=END
                elif c==ESC_ESC:c=ESC
                else:self.data.clear()
                self.escaped=False
            elif c==ESC:self.escaped=True;continue
            if len(self.data)<4096:self.data.append(c)
            else:self.data.clear();self.escaped=False
        return frames


def enter_slip(port):
    port.reset_input_buffer();port.write(b"slip on\n");port.flush();time.sleep(.3);port.reset_input_buffer()


def run(args):
    if not elevated():raise PermissionError("Run as Administrator so Wintun can create/configure the adapter")
    tun=Wintun(ROOT/"wintun"/"amd64"/"wintun.dll",args.adapter)
    port=serial.Serial(args.port,115200,timeout=.02,write_timeout=5);time.sleep(.4);enter_slip(port)
    configure(tun.index,args.local_ip,args.remote_ip)
    print(f"READY SLIP adapter={args.adapter} ifIndex={tun.index} {args.local_ip}/32 route={args.remote_ip}/32 port={args.port}",flush=True)
    stop=threading.Event();outbound=queue.Queue(maxsize=args.queue_size);rx_ipv4=threading.Event();decoder=SlipDecoder();lock=threading.Lock()
    stats={"captured":0,"filtered":0,"tx_slip":0,"rx_slip":0,"invalid_slip":0,"queue_drops":0,"queue_high_water":0,"turnaround_timeouts":0}
    started=time.monotonic();last_stats=started
    def count(key,value=1):
        with lock:stats[key]+=value
    def show_stats():
        with lock:snapshot=dict(stats)
        print("SLIP_STATS "+" ".join(f"{k}={v}" for k,v in snapshot.items())+f" queue_now={outbound.qsize()} uptime_s={time.monotonic()-started:.1f}",flush=True)
    def serial_to_tun():
        while not stop.is_set():
            try:data=port.read(max(1,port.in_waiting))
            except serial.SerialException as error:print(f"SERIAL ERROR: {error}",flush=True);stop.set();return
            for packet in decoder.feed(data):
                if valid_ipv4(packet):tun.inject(packet);rx_ipv4.set();count("rx_slip");print(f"RX SLIP IPv4 {len(packet)} bytes -> Wintun",flush=True)
                else:count("invalid_slip")
    def tun_to_slip():
        while not stop.is_set():
            try:packet=outbound.get(timeout=.1)
            except queue.Empty:continue
            rx_ipv4.clear()
            try:port.write(slip_encode(packet));port.flush();count("tx_slip");print(f"TX IPv4 {len(packet)} bytes -> SLIP",flush=True)
            except (serial.SerialException,serial.SerialTimeoutException) as error:print(f"SERIAL ERROR: {error}",flush=True);stop.set();return
            if args.turnaround>0 and not rx_ipv4.wait(args.turnaround):count("turnaround_timeouts");print(f"TURNAROUND {args.turnaround}s expired",flush=True)
            outbound.task_done()
    threads=[threading.Thread(target=serial_to_tun,daemon=True),threading.Thread(target=tun_to_slip,daemon=True)]
    for thread in threads:thread.start()
    try:
        while not stop.is_set():
            packet=tun.receive()
            if packet and allowed_outbound(packet,args.remote_ip,args.udp_port,args.pass_all):
                count("captured")
                try:
                    outbound.put_nowait(packet)
                    with lock:stats["queue_high_water"]=max(stats["queue_high_water"],outbound.qsize())
                except queue.Full:count("queue_drops");print("DROP: outbound SLIP queue full",flush=True)
            elif packet:count("filtered")
            else:time.sleep(.005)
            if args.stats_interval>0 and time.monotonic()-last_stats>=args.stats_interval:last_stats=time.monotonic();show_stats()
    except KeyboardInterrupt:pass
    finally:
        stop.set()
        for thread in threads:thread.join(.5)
        port.close();tun.close();show_stats()


def main():
    p=argparse.ArgumentParser(description="Wintun <-> USB CDC SLIP <-> reliable acoustic AX.25 bridge")
    p.add_argument("--port",default="COM5");p.add_argument("--adapter",default="AcousticSLIP Tunnel")
    p.add_argument("--local-ip",default="10.23.0.1");p.add_argument("--remote-ip",default="10.23.0.2")
    p.add_argument("--udp-port",type=int,default=7000);p.add_argument("--queue-size",type=int,default=32)
    p.add_argument("--turnaround",type=float,default=15);p.add_argument("--stats-interval",type=float,default=30);p.add_argument("--pass-all",action="store_true")
    run(p.parse_args())


if __name__=="__main__":main()
