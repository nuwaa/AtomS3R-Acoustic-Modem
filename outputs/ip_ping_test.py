"""Two-port automated user-space IPv4 ICMP Echo acceptance test."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import acoustic_ping as net
import serial


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--a",default="COM5");parser.add_argument("--b",default="COM6");args=parser.parse_args()
    folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-ipv4-icmp");folder.mkdir(parents=True)
    a=serial.Serial(args.a,115200,timeout=.03);b=serial.Serial(args.b,115200,timeout=.03);time.sleep(.5)
    a.reset_input_buffer();b.reset_input_buffer();ra=net.SerialLines(a);rb=net.SerialLines(b)
    identifier=0x1234;sequence=1;payload=b"acoustic IPv4 ICMP test"+bytes(range(32))
    request=net.ipv4_icmp("10.23.0.1","10.23.0.2",8,identifier,sequence,payload)
    started=time.monotonic();net.send_ipv4(a,request);replied=False;received=False;events=[];deadline=started+60
    try:
        while time.monotonic()<deadline and not received:
            for packet in net.packets(rb.poll()):
                parsed=net.parse_icmp(packet)
                if parsed and parsed["type"]==8 and parsed["destination"]=="10.23.0.2":
                    events.append("B received valid echo request")
                    reply=net.ipv4_icmp("10.23.0.2","10.23.0.1",0,parsed["id"],parsed["sequence"],parsed["payload"])
                    net.send_ipv4(b,reply);replied=True
            for packet in net.packets(ra.poll()):
                parsed=net.parse_icmp(packet)
                if parsed and parsed["type"]==0 and parsed["id"]==identifier and parsed["sequence"]==sequence and parsed["payload"]==payload:
                    received=True;events.append("A received valid echo reply")
            time.sleep(.01)
    finally:a.close();b.close()
    result={"pass":bool(replied and received),"request_bytes":len(request),"rtt_ms":round((time.monotonic()-started)*1000),"events":events,"A":args.a,"B":args.b}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if result["pass"] else "FAIL",result)
    raise SystemExit(0 if result["pass"] else 1)


if __name__=="__main__":main()
