"""Queue acceptance test: enqueue UDP datagrams without waiting for replies."""
import argparse,json,socket,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument("--target",default="10.23.0.2");p.add_argument("--port",type=int,default=7000);p.add_argument("--count",type=int,default=5);p.add_argument("--size",type=int,default=64);p.add_argument("--timeout",type=float,default=120);a=p.parse_args()
    sent={i:i.to_bytes(4,"big")+bytes((x+i)&255 for x in range(a.size-4)) for i in range(a.count)};received={};duplicates=[]
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(.5);started=time.monotonic()
    try:
        for payload in sent.values():sock.sendto(payload,(a.target,a.port))
        deadline=started+a.timeout
        while time.monotonic()<deadline and len(received)<len(sent):
            try:data,peer=sock.recvfrom(2048)
            except socket.timeout:continue
            if len(data)<4:continue
            sequence=int.from_bytes(data[:4],"big")
            if sequence in received:duplicates.append(sequence)
            received[sequence]={"bytes":len(data),"match":sent.get(sequence)==data,"peer":list(peer),"at_ms":round((time.monotonic()-started)*1000)}
    finally:sock.close()
    passed=set(received)==set(sent) and all(x["match"] for x in received.values()) and not duplicates
    folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-windows-udp-burst");folder.mkdir(parents=True)
    result={"pass":passed,"sent":a.count,"received":len(received),"size":a.size,"order":list(received),"duplicates":duplicates,"packets":received}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL",result);raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
