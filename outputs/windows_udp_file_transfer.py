"""Reliable file transfer demo over ordinary Windows UDP sockets and acoustic AX.25."""
import argparse,hashlib,json,os,socket,struct,time
from pathlib import Path

MAGIC=b"AUF1"

def request(sock,target,payload,transfer_id,retries,discard_first=False):
    for attempt in range(1,retries+1):
        sock.sendto(payload,target)
        try:data,_=sock.recvfrom(2048)
        except socket.timeout:continue
        if len(data)>=14 and data[:5]==MAGIC+b"A" and struct.unpack("!I",data[5:9])[0]==transfer_id:
            if discard_first:discard_first=False;print("simulated ACK loss; retransmitting",flush=True);continue
            return data,attempt
    raise TimeoutError("file-transfer acknowledgement timed out")

def main():
    p=argparse.ArgumentParser();p.add_argument("file",type=Path);p.add_argument("--target",default="10.23.0.2");p.add_argument("--port",type=int,default=7000)
    p.add_argument("--chunk",type=int,default=128);p.add_argument("--timeout",type=float,default=90);p.add_argument("--retries",type=int,default=4)
    p.add_argument("--simulate-ack-loss",action="store_true",help="discard the first data ACK once to verify idempotent retry");a=p.parse_args()
    data=a.file.read_bytes()
    if not data or len(data)>65535:p.error("file size must be 1..65535 bytes")
    if not 32<=a.chunk<=1200:p.error("--chunk must be 32..1200")
    digest=hashlib.sha256(data).digest();transfer_id=int.from_bytes(os.urandom(4),"big");target=(a.target,a.port)
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(a.timeout);started=time.monotonic();attempts=0
    try:
        reply,n=request(sock,target,MAGIC+b"S"+struct.pack("!II",transfer_id,len(data))+digest+a.file.name.encode("utf-8"),transfer_id,a.retries);attempts+=n
        if reply[13]!=0:raise RuntimeError("receiver rejected transfer start")
        offset=0;simulate=a.simulate_ack_loss
        while offset<len(data):
            chunk=data[offset:offset+a.chunk];reply,n=request(sock,target,MAGIC+b"D"+struct.pack("!II",transfer_id,offset)+chunk,transfer_id,a.retries,simulate);attempts+=n;simulate=False
            next_offset,status=struct.unpack("!IB",reply[9:14])
            if status==2:raise RuntimeError(f"receiver rejected data at offset {offset}")
            offset=next_offset;print(f"{offset}/{len(data)} bytes",flush=True)
        remote_digest=reply[14:46] if len(reply)>=46 else b"";passed=status==1 and remote_digest==digest
    finally:sock.close()
    result={"pass":passed,"file":str(a.file),"bytes":len(data),"sha256":digest.hex(),"datagrams":1+(len(data)+a.chunk-1)//a.chunk,
            "udp_attempts":attempts,"elapsed_ms":round((time.monotonic()-started)*1000),"target":f"{a.target}:{a.port}"}
    folder=Path(__file__).resolve().parent/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-windows-udp-file");folder.mkdir(parents=True)
    (folder/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8");print("Saved:",folder);print("PASS" if passed else "FAIL",result)
    raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
