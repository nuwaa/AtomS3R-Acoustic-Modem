"""Sequential Windows UDP stability test over the active acoustic IP bridge."""
import argparse,json,socket,statistics,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument("--target",default="10.23.0.2");p.add_argument("--port",type=int,default=7000)
    p.add_argument("--count",type=int,default=50);p.add_argument("--size",type=int,default=32);p.add_argument("--timeout",type=float,default=60);a=p.parse_args()
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(a.timeout);items=[];started=time.monotonic()
    try:
        for sequence in range(a.count):
            payload=sequence.to_bytes(4,"big")+bytes((sequence*17+i)&255 for i in range(a.size-4));began=time.monotonic();error=None;match=False
            try:sock.sendto(payload,(a.target,a.port));reply,peer=sock.recvfrom(2048);match=reply==payload
            except socket.timeout:error="timeout"
            elapsed=round((time.monotonic()-began)*1000);item={"sequence":sequence,"pass":match,"rtt_ms":elapsed,"error":error};items.append(item)
            print(f"{sequence+1}/{a.count} {'PASS' if match else 'FAIL'} {elapsed}ms",flush=True)
    finally:sock.close()
    good=[x["rtt_ms"] for x in items if x["pass"]];passed=len(good)==a.count
    result={"pass":passed,"sent":a.count,"received_exact":len(good),"loss_or_mismatch":a.count-len(good),"size":a.size,
            "elapsed_ms":round((time.monotonic()-started)*1000),"rtt_ms":None if not good else {"min":min(good),"average":round(statistics.mean(good)),"max":max(good),"median":round(statistics.median(good))},"packets":items}
    folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-windows-udp-stability");folder.mkdir(parents=True)
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL",result);raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
