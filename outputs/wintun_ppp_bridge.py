"""Bridge Windows Wintun IPv4 to USB CDC PPP and reliable acoustic AX.25."""
import argparse,json,queue,struct,sys,threading,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"environment/settings.json").read_text(encoding="utf-8"));sys.path.insert(0,CFG["python_libraries"])
import serial
from ppp_udp_test import FLAG,ESC,GOOD_FCS,control,encode,fcs16
from wintun_bridge import Wintun,allowed_outbound,configure,elevated,valid_ipv4


class Decoder:
    def __init__(self):self.data=bytearray();self.escaped=False;self.bad_fcs=0
    def feed(self,data):
        frames=[]
        for c in data:
            if c==FLAG:
                if self.data:
                    if len(self.data)>=6 and fcs16(self.data)==GOOD_FCS:frames.append(bytes(self.data[:-2]))
                    else:self.bad_fcs+=1
                self.data.clear();self.escaped=False;continue
            if self.escaped:c^=0x20;self.escaped=False
            elif c==ESC:self.escaped=True;continue
            if len(self.data)<4096:self.data.append(c)
            else:self.data.clear();self.escaped=False;self.bad_fcs+=1
        return frames


class PppPeer:
    def __init__(self,port,write_lock,network,stats,stats_lock):
        self.port=port;self.write_lock=write_lock;self.network=network;self.stats=stats;self.stats_lock=stats_lock;self.decoder=Decoder();self.reset()
    def count(self,key,value=1):
        with self.stats_lock:self.stats[key]+=value
    def write(self,protocol,info):
        with self.write_lock:self.port.write(encode(protocol,info));self.port.flush()
        self.count("ppp_tx_frames")
    def reset(self):self.lcp_request=self.lcp_ack=self.ipcp_request=self.ipcp_ack=self.ipcp_sent=False;self.network.clear()
    def start(self):self.reset();self.write(0xc021,control(1,0x41,b"\x01\x04\x05\xdc"))
    def feed(self,data):
        before=self.decoder.bad_fcs;frames=self.decoder.feed(data)
        if self.decoder.bad_fcs>before:self.count("ppp_bad_fcs",self.decoder.bad_fcs-before)
        ipv4=[]
        for frame in frames:
            self.count("ppp_rx_frames")
            if not frame.startswith(b"\xff\x03") or len(frame)<4:continue
            protocol=struct.unpack("!H",frame[2:4])[0];info=frame[4:]
            if protocol in (0xc021,0x8021) and len(info)>=4:
                code,identifier=info[0],info[1];length=struct.unpack("!H",info[2:4])[0]
                if length<4 or length>len(info):continue
                message=info[:length];self.count("ppp_control")
                if code==1:
                    self.write(protocol,bytes((2,))+message[1:])
                    if protocol==0xc021:self.lcp_request=True
                    else:self.ipcp_request=True
                elif code==2 and protocol==0xc021 and identifier==0x41:self.lcp_ack=True
                elif code==2 and protocol==0x8021 and identifier==0x42:self.ipcp_ack=True
                elif code==5:self.write(protocol,bytes((6,))+message[1:]);self.reset();self.count("ppp_reconnects")
            elif protocol==0x0021 and valid_ipv4(info):ipv4.append(info)
            if self.lcp_request and self.lcp_ack and not self.ipcp_sent:
                self.write(0x8021,control(1,0x42,b"\x03\x06\x0a\x17\x00\x01"));self.ipcp_sent=True
            if self.ipcp_request and self.ipcp_ack and not self.network.is_set():self.network.set();self.count("ppp_open")
        return ipv4


def run(args):
    if not elevated():raise PermissionError("Run as Administrator so Wintun can create/configure the adapter")
    port=serial.Serial(args.port,115200,timeout=.02,write_timeout=5);tun=None;interrupted=False;disconnected=threading.Event();time.sleep(.4)
    try:tun=Wintun(ROOT/"wintun"/"amd64"/"wintun.dll",args.adapter)
    except Exception:
        port.close();raise
    try:
        port.reset_input_buffer();port.write(b"mode ppp\n");port.flush();time.sleep(.25)
        configure(tun.index,args.local_ip,args.remote_ip)
    except Exception:
        port.close();tun.close();raise
    stop=threading.Event();network=threading.Event();rx_ipv4=threading.Event();write_lock=threading.Lock();stats_lock=threading.Lock();outbound=queue.Queue(maxsize=args.queue_size)
    stats={"captured":0,"filtered":0,"tx_ipv4":0,"rx_ipv4":0,"ppp_tx_frames":0,"ppp_rx_frames":0,"ppp_control":0,"ppp_bad_fcs":0,
           "ppp_open":0,"ppp_reconnects":0,"queue_drops":0,"queue_high_water":0,"turnaround_timeouts":0};peer=PppPeer(port,write_lock,network,stats,stats_lock)
    try:
        peer.start();negotiation_deadline=time.monotonic()+args.negotiation_timeout
        while not network.is_set() and time.monotonic()<negotiation_deadline:peer.feed(port.read(max(1,port.in_waiting)))
        if not network.is_set():raise TimeoutError("PPP LCP/IPCP negotiation timed out")
    except Exception:
        port.close();tun.close();raise
    print(f"READY PPP adapter={args.adapter} ifIndex={tun.index} {args.local_ip}/32 route={args.remote_ip}/32 port={args.port}",flush=True)
    started=time.monotonic();last_stats=started
    def count(key,value=1):
        with stats_lock:stats[key]+=value
    def show():
        with stats_lock:snapshot=dict(stats)
        print("PPP_STATS "+" ".join(f"{k}={v}" for k,v in snapshot.items())+f" queue_now={outbound.qsize()} network_open={int(network.is_set())} uptime_s={time.monotonic()-started:.1f}",flush=True)
    def serial_reader():
        while not stop.is_set():
            try:data=port.read(max(1,port.in_waiting))
            except (serial.SerialException,OSError) as error:print(f"SERIAL DISCONNECTED: {error}",flush=True);disconnected.set();stop.set();return
            for packet in peer.feed(data):tun.inject(packet);rx_ipv4.set();count("rx_ipv4");print(f"RX PPP IPv4 {len(packet)} bytes -> Wintun",flush=True)
    def sender():
        while not stop.is_set():
            try:packet=outbound.get(timeout=.1)
            except queue.Empty:continue
            if not network.wait(args.negotiation_timeout):count("turnaround_timeouts");outbound.task_done();continue
            rx_ipv4.clear()
            try:peer.write(0x0021,packet)
            except (serial.SerialException,OSError) as error:print(f"SERIAL DISCONNECTED: {error}",flush=True);disconnected.set();stop.set();outbound.task_done();return
            count("tx_ipv4");print(f"TX IPv4 {len(packet)} bytes -> PPP",flush=True)
            if args.turnaround>0 and not rx_ipv4.wait(args.turnaround):count("turnaround_timeouts");print(f"TURNAROUND {args.turnaround}s expired",flush=True)
            outbound.task_done()
    threads=[threading.Thread(target=serial_reader,daemon=True),threading.Thread(target=sender,daemon=True)]
    for t in threads:t.start()
    try:
        while not stop.is_set():
            packet=tun.receive()
            if packet and allowed_outbound(packet,args.remote_ip,args.udp_port,args.pass_all):
                count("captured")
                try:
                    outbound.put_nowait(packet)
                    with stats_lock:stats["queue_high_water"]=max(stats["queue_high_water"],outbound.qsize())
                except queue.Full:count("queue_drops");print("DROP: outbound PPP queue full",flush=True)
            elif packet:count("filtered")
            else:time.sleep(.005)
            if args.stats_interval>0 and time.monotonic()-last_stats>=args.stats_interval:last_stats=time.monotonic();show()
    except KeyboardInterrupt:interrupted=True
    finally:
        stop.set()
        for t in threads:t.join(.5)
        try:port.close()
        except Exception:pass
        if tun is not None:tun.close()
        show()
    return disconnected.is_set() and not interrupted


def main():
    p=argparse.ArgumentParser(description="Wintun <-> USB CDC PPP <-> reliable acoustic AX.25 bridge")
    p.add_argument("--port",default="COM5");p.add_argument("--adapter",default="AcousticPPP Tunnel");p.add_argument("--local-ip",default="10.23.0.1");p.add_argument("--remote-ip",default="10.23.0.2")
    p.add_argument("--udp-port",type=int,default=7000);p.add_argument("--queue-size",type=int,default=32);p.add_argument("--turnaround",type=float,default=15)
    p.add_argument("--stats-interval",type=float,default=30);p.add_argument("--negotiation-timeout",type=float,default=10);p.add_argument("--pass-all",action="store_true")
    p.add_argument("--reconnect-delay",type=float,default=2,help="seconds between USB serial reconnect attempts")
    p.add_argument("--no-auto-reconnect",action="store_true",help="exit after a serial disconnect")
    args=p.parse_args();attempt=0
    while True:
        try:reconnect=run(args)
        except KeyboardInterrupt:break
        except (serial.SerialException,OSError,TimeoutError) as error:
            reconnect=True;print(f"RECONNECT pending: {type(error).__name__}: {error}",flush=True)
        if args.no_auto_reconnect or not reconnect:break
        attempt+=1;print(f"RECONNECT attempt={attempt} port={args.port} in {args.reconnect_delay:g}s",flush=True);time.sleep(args.reconnect_delay)

if __name__=="__main__":main()
