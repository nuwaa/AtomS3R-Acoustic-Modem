"""Interactive text demo using ordinary Windows UDP sockets over Wintun."""
import argparse,socket

def main():
    p=argparse.ArgumentParser();p.add_argument("--target",default="10.23.0.2");p.add_argument("--port",type=int,default=7000);p.add_argument("--timeout",type=float,default=60);a=p.parse_args()
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.settimeout(a.timeout)
    print("UTF-8 textを入力してください。空行で終了します。")
    try:
        while True:
            text=input("> ")
            if not text:break
            data=text.encode("utf-8");sock.sendto(data,(a.target,a.port));reply,peer=sock.recvfrom(2048)
            print(f"{peer[0]}:{peer[1]} < {reply.decode('utf-8','replace')}")
    finally:sock.close()

if __name__=="__main__":main()
