"""Negotiate LCP/IPCP with ATOM over USB CDC PPP and test IPv4/UDP echo."""
import argparse,json,struct,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import acoustic_ip_endpoint as ip
import acoustic_ping as link

FLAG=0x7e;ESC=0x7d;GOOD_FCS=0xf0b8

def fcs16(data):
    value=0xffff
    for c in data:
        value^=c
        for _ in range(8):value=(value>>1)^0x8408 if value&1 else value>>1
    return value

def encode(protocol,information,corrupt_fcs=False):
    raw=bytearray(b"\xff\x03"+struct.pack("!H",protocol)+information);f=fcs16(raw)^0xffff;raw+=struct.pack("<H",f);out=bytearray([FLAG])
    if corrupt_fcs:raw[-1]^=1
    for c in raw:
        if c<0x20 or c in (FLAG,ESC):out.extend((ESC,c^0x20))
        else:out.append(c)
    out.append(FLAG);return bytes(out)

class Decoder:
    def __init__(self):self.data=bytearray();self.escaped=False
    def feed(self,data):
        frames=[]
        for c in data:
            if c==FLAG:
                if len(self.data)>=6 and fcs16(self.data)==GOOD_FCS:frames.append(bytes(self.data[:-2]))
                self.data.clear();self.escaped=False;continue
            if self.escaped:c^=0x20;self.escaped=False
            elif c==ESC:self.escaped=True;continue
            if len(self.data)<4096:self.data.append(c)
            else:self.data.clear();self.escaped=False
        return frames

def control(code,identifier,options=b""):return bytes((code,identifier))+struct.pack("!H",4+len(options))+options

def main():
    p=argparse.ArgumentParser();p.add_argument("--port",default="COM5");p.add_argument("--timeout",type=float,default=90);p.add_argument("--skip-bad-fcs",action="store_true");a=p.parse_args()
    serial=link.serial.Serial(a.port,115200,timeout=.03);time.sleep(.5);serial.reset_input_buffer();serial.write(b"mode ppp\n");serial.flush();decoder=Decoder();time.sleep(.2)
    serial.write(encode(0xc021,control(1,0x41,b"\x01\x04\x05\xdc")));serial.flush()
    lcp_request=False;lcp_ack=False;ipcp_request=False;ipcp_ack=False;ipcp_sent=False;network_started=None;received=None;bad_replied=False;bad_sent_at=None;valid_sent=False
    payload=b"PPP-UDP-"+bytes((0x7e,0x7d,0,1,2,3));packet=ip.ipv4_udp("10.23.0.1","10.23.0.2",7401,7000,payload,0x5001)
    bad_payload=b"PPP-BAD-FCS";bad_packet=ip.ipv4_udp("10.23.0.1","10.23.0.2",7401,7000,bad_payload,0x5000)
    started=time.monotonic();deadline=started+a.timeout
    try:
        while time.monotonic()<deadline and received is None:
            data=serial.read(max(1,serial.in_waiting))
            for frame in decoder.feed(data):
                if not frame.startswith(b"\xff\x03") or len(frame)<4:continue
                protocol=struct.unpack("!H",frame[2:4])[0];info=frame[4:]
                if protocol in (0xc021,0x8021) and len(info)>=4:
                    code,identifier=info[0],info[1];length=struct.unpack("!H",info[2:4])[0];message=info[:length]
                    if code==1:
                        serial.write(encode(protocol,bytes((2,))+message[1:]));serial.flush()
                        if protocol==0xc021:lcp_request=True
                        else:ipcp_request=True
                    elif code==2 and protocol==0xc021 and identifier==0x41:lcp_ack=True
                    elif code==2 and protocol==0x8021 and identifier==0x42:ipcp_ack=True
                elif protocol==0x0021:
                    udp=ip.parse_udp(info)
                    if udp and udp["payload"]==bad_payload:bad_replied=True
                    if udp and udp["source"]=="10.23.0.2" and udp["destination"]=="10.23.0.1" and udp["payload"]==payload:received=info
            if lcp_request and lcp_ack and not ipcp_sent:
                serial.write(encode(0x8021,control(1,0x42,b"\x03\x06\x0a\x17\x00\x01")));serial.flush();ipcp_sent=True
            if ipcp_request and ipcp_ack and network_started is None:
                network_started=time.monotonic()
                if a.skip_bad_fcs:serial.write(encode(0x0021,packet));serial.flush();valid_sent=True
                else:serial.write(encode(0x0021,bad_packet,True));serial.flush();bad_sent_at=time.monotonic()
            if network_started is not None and not valid_sent and time.monotonic()-bad_sent_at>=6:
                serial.write(encode(0x0021,packet));serial.flush();valid_sent=True
    finally:serial.close()
    passed=received is not None;folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-ppp-udp");folder.mkdir(parents=True)
    result={"pass":passed,"lcp":{"peer_request_acked":lcp_request,"our_request_acked":lcp_ack},
            "ipcp":{"peer_request_acked":ipcp_request,"our_request_acked":ipcp_ack},"ipv4_bytes":len(packet),
            "bad_fcs_rejected":None if a.skip_bad_fcs else not bad_replied,
            "payload_hex":payload.hex(),"negotiation_ms":None if network_started is None else round((network_started-started)*1000),
            "udp_rtt_ms":None if received is None or network_started is None else round((time.monotonic()-network_started)*1000)}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL",result);raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
