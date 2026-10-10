"""Reliable peer-to-peer UTF-8 chat over ordinary UDP/IP."""
from __future__ import annotations
import argparse,queue,socket,threading,time
import chat_protocol as protocol

def endpoint(value):
    host,separator,port=value.rpartition(":")
    if not separator or not host:return argparse.ArgumentTypeError("use HOST:PORT")
    try:number=int(port)
    except ValueError:raise argparse.ArgumentTypeError("invalid port")
    if not 1<=number<=65535:raise argparse.ArgumentTypeError("invalid port")
    return host,number

class UdpChatTransport:
    def __init__(self,bind,peer,on_chat):
        self.peer=peer;self.on_chat=on_chat;self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(bind);self.socket.settimeout(.2);self.stop=threading.Event();self.acks={};self.lock=threading.Lock();self.seen={}
        self.thread=threading.Thread(target=self._receive,daemon=True)
    def start(self):self.thread.start()
    def close(self):self.stop.set();self.thread.join(1);self.socket.close()
    def _receive(self):
        while not self.stop.is_set():
            try:data,address=self.socket.recvfrom(2048)
            except socket.timeout:continue
            except OSError:return
            try:message=protocol.decode(data)
            except (ValueError,UnicodeError):continue
            if message["type"]=="ack":
                with self.lock:event=self.acks.get(message["ack_id"])
                if event:event.set()
                continue
            identifier=message["id"];self.socket.sendto(protocol.encode(protocol.ack(identifier)),address)
            now=time.monotonic();duplicate=identifier in self.seen;self.seen[identifier]=now
            if not duplicate:self.on_chat(message,address)
            if len(self.seen)>512:
                cutoff=now-3600;self.seen={key:value for key,value in self.seen.items() if value>=cutoff}
    def send(self,sender,text,attempts=4,timeout=2):
        message=protocol.chat(sender,text);identifier=message["id"];event=threading.Event()
        with self.lock:self.acks[identifier]=event
        try:
            data=protocol.encode(message)
            for attempt in range(1,attempts+1):
                self.socket.sendto(data,self.peer)
                if event.wait(timeout):return identifier,attempt
            raise TimeoutError(f"no ACK after {attempts} attempts")
        finally:
            with self.lock:self.acks.pop(identifier,None)

def main():
    parser=argparse.ArgumentParser(description="Transport-independent UTF-8 UDP chat (ATOM not required)")
    parser.add_argument("--name",default=socket.gethostname());parser.add_argument("--bind",type=endpoint,default=("0.0.0.0",7700))
    parser.add_argument("--peer",type=endpoint,required=True);parser.add_argument("--send");parser.add_argument("--listen-seconds",type=float)
    parser.add_argument("--ack-timeout",type=float,default=2);parser.add_argument("--attempts",type=int,default=4);args=parser.parse_args()
    def received(message,address):print(f"\n{message['sender']}@{address[0]}: {message['text']}",flush=True)
    transport=UdpChatTransport(args.bind,args.peer,received);transport.start()
    print(f"READY IP CHAT name={args.name} bind={args.bind[0]}:{args.bind[1]} peer={args.peer[0]}:{args.peer[1]}",flush=True)
    try:
        if args.send is not None:
            identifier,attempt=transport.send(args.name,args.send,args.attempts,args.ack_timeout);print(f"SENT ACK id={identifier} attempt={attempt}")
        elif args.listen_seconds is not None:time.sleep(args.listen_seconds)
        else:
            print("UTF-8 textを入力してください。空行で終了します。")
            while True:
                text=input("> ")
                if not text:break
                try:identifier,attempt=transport.send(args.name,text,args.attempts,args.ack_timeout);print(f"ACK attempt={attempt} id={identifier}")
                except TimeoutError as error:print("SEND FAILED:",error)
    except KeyboardInterrupt:pass
    finally:transport.close()

if __name__=="__main__":main()
