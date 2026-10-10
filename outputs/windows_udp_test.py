"""Windows standard socket UDP Echo test over Wintun/acoustic AX.25."""
import argparse,json,socket,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--target",default="10.23.0.2");parser.add_argument("--port",type=int,default=7000);parser.add_argument("--count",type=int,default=3);parser.add_argument("--size",type=int,default=96);args=parser.parse_args()
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(30);results=[]
    try:
        for sequence in range(args.count):
            payload=sequence.to_bytes(4,"big")+bytes((index+sequence)&255 for index in range(args.size-4));started=time.monotonic();sock.sendto(payload,(args.target,args.port))
            try:data,peer=sock.recvfrom(2048);rtt=round((time.monotonic()-started)*1000);ok=data==payload and peer==(args.target,args.port)
            except socket.timeout:data=b"";peer=None;rtt=None;ok=False
            results.append({"sequence":sequence,"bytes":len(data),"rtt_ms":rtt,"match":ok});print(f"seq={sequence} bytes={len(data)} rtt={rtt}ms match={ok}",flush=True)
    finally:sock.close()
    passed=all(item["match"] for item in results);folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-windows-udp");folder.mkdir(parents=True)
    result={"pass":passed,"target":f"{args.target}:{args.port}","payload_bytes":args.size,"results":results}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL");raise SystemExit(0 if passed else 1)


if __name__=="__main__":main()
