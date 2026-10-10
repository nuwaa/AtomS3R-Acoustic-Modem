"""Send one IPv4/UDP echo through USB CDC SLIP and acoustic AX.25."""
import argparse,json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import acoustic_ip_endpoint as ip
import acoustic_ping as link

END=0xc0;ESC=0xdb;ESC_END=0xdc;ESC_ESC=0xdd

def encode(data):
    out=bytearray([END])
    for c in data:
        if c==END:out.extend((ESC,ESC_END))
        elif c==ESC:out.extend((ESC,ESC_ESC))
        else:out.append(c)
    out.append(END);return bytes(out)

class Decoder:
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
            self.data.append(c)
        return frames

def main():
    p=argparse.ArgumentParser();p.add_argument("--port",default="COM5");p.add_argument("--timeout",type=float,default=90);a=p.parse_args()
    payload=b"SLIP-UDP-"+bytes((0xc0,0xdb,0,1,2,3));packet=ip.ipv4_udp("10.23.0.1","10.23.0.2",7301,7000,payload,0x5101)
    serial=link.serial.Serial(a.port,115200,timeout=.05);time.sleep(.5);serial.reset_input_buffer();serial.write(b"slip on\n");serial.flush();time.sleep(.3);serial.reset_input_buffer()
    started=time.monotonic();serial.write(encode(packet));serial.flush();decoder=Decoder();received=None;deadline=started+a.timeout
    try:
        while time.monotonic()<deadline and received is None:
            data=serial.read(max(1,serial.in_waiting))
            for frame in decoder.feed(data):
                udp=ip.parse_udp(frame)
                if udp and udp["source"]=="10.23.0.2" and udp["destination"]=="10.23.0.1" and udp["payload"]==payload:received=frame;break
    finally:serial.close()
    passed=received is not None;folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-slip-udp");folder.mkdir(parents=True)
    result={"pass":passed,"request_ipv4_bytes":len(packet),"payload_hex":payload.hex(),"rtt_ms":round((time.monotonic()-started)*1000)}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL",result);raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
