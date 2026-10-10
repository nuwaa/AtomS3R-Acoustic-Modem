"""Zero-dependency HTTP/WebSocket gateway for the reliable UDP chat transport."""
from __future__ import annotations
import argparse,base64,hashlib,json,socket,struct,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from ip_chat import UdpChatTransport,endpoint
import chat_protocol as protocol

ROOT=Path(__file__).resolve().parent
GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def exact(stream,count):
    data=bytearray()
    while len(data)<count:
        block=stream.read(count-len(data))
        if not block:raise EOFError
        data.extend(block)
    return bytes(data)

class WebSocketClient:
    def __init__(self,connection,stream):self.connection=connection;self.stream=stream;self.lock=threading.Lock();self.closed=False
    def send(self,message):
        payload=json.dumps(message,ensure_ascii=False,separators=(",",":")).encode("utf-8");length=len(payload)
        header=bytes((0x81,length)) if length<126 else bytes((0x81,126))+struct.pack("!H",length) if length<=65535 else bytes((0x81,127))+struct.pack("!Q",length)
        with self.lock:
            if self.closed:return
            try:self.connection.sendall(header+payload)
            except OSError:self.closed=True
    def receive(self):
        first,second=exact(self.stream,2);opcode=first&15;masked=bool(second&128);length=second&127
        if length==126:length=struct.unpack("!H",exact(self.stream,2))[0]
        elif length==127:length=struct.unpack("!Q",exact(self.stream,8))[0]
        if length>65536:raise ValueError("WebSocket frame too large")
        mask=exact(self.stream,4) if masked else None;payload=bytearray(exact(self.stream,length))
        if mask:
            for index in range(length):payload[index]^=mask[index%4]
        if opcode==8:raise EOFError
        if opcode==9:
            with self.lock:self.connection.sendall(bytes((0x8a,len(payload)))+payload)
            return None
        if opcode!=1:return None
        return json.loads(payload.decode("utf-8"))
    def close(self):
        self.closed=True
        try:self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:pass

class Gateway:
    def __init__(self,name,udp_bind,udp_peer):
        self.name=name;self.clients=set();self.lock=threading.Lock();self.transport=UdpChatTransport(udp_bind,udp_peer,self.received_udp)
    def start(self):self.transport.start()
    def close(self):self.transport.close()
    def add(self,client):
        with self.lock:self.clients.add(client)
        client.send({"type":"status","state":"connected","name":self.name})
    def remove(self,client):
        with self.lock:self.clients.discard(client)
        client.close()
    def broadcast(self,message):
        with self.lock:clients=list(self.clients)
        for client in clients:client.send(message)
    def received_udp(self,message,address):
        self.broadcast({"type":"chat","direction":"received","id":message["id"],"sender":message["sender"],"text":message["text"],"address":address[0]})
    def browser_message(self,client,message):
        if not isinstance(message,dict) or message.get("type")!="send":return
        sender=str(message.get("sender") or self.name);text=message.get("text")
        try:
            if self.transport.peer is None:
                local=protocol.chat(sender,text);self.broadcast({"type":"chat","direction":"received","id":local["id"],"sender":sender,"text":text,"address":"local-room"});return
            identifier,attempt=self.transport.send(sender,text)
            event={"type":"chat","direction":"sent","id":identifier,"sender":sender,"text":text,"attempt":attempt}
            self.broadcast(event)
        except (ValueError,TimeoutError,OSError) as error:client.send({"type":"error","message":str(error)})

class Handler(BaseHTTPRequestHandler):
    server_version="AtomIPChat/1"
    def log_message(self,format,*args):print(f"HTTP {self.client_address[0]} "+format%args,flush=True)
    def do_GET(self):
        if self.path=="/ws" and self.headers.get("Upgrade","").lower()=="websocket":return self.websocket()
        if self.path not in ("/","/index.html"):
            self.send_error(404);return
        data=(ROOT/"web_chat"/"index.html").read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
    def websocket(self):
        key=self.headers.get("Sec-WebSocket-Key")
        if not key:self.send_error(400);return
        accept=base64.b64encode(hashlib.sha1((key+GUID).encode("ascii")).digest()).decode("ascii")
        self.send_response(101);self.send_header("Upgrade","websocket");self.send_header("Connection","Upgrade");self.send_header("Sec-WebSocket-Accept",accept);self.end_headers()
        client=WebSocketClient(self.connection,self.rfile);self.server.gateway.add(client)
        try:
            while True:
                message=client.receive()
                if message is not None:self.server.gateway.browser_message(client,message)
        except (EOFError,OSError,ValueError,json.JSONDecodeError):pass
        finally:self.server.gateway.remove(client)

def main():
    parser=argparse.ArgumentParser(description="Browser WebSocket gateway for IP chat")
    parser.add_argument("--name",default=socket.gethostname());parser.add_argument("--http-bind",type=endpoint,default=("127.0.0.1",8080))
    parser.add_argument("--udp-bind",type=endpoint,default=("0.0.0.0",7700));parser.add_argument("--udp-peer",type=endpoint);args=parser.parse_args()
    gateway=Gateway(args.name,args.udp_bind,args.udp_peer);server=ThreadingHTTPServer(args.http_bind,Handler);server.gateway=gateway;gateway.start()
    peer="local-room" if args.udp_peer is None else f"{args.udp_peer[0]}:{args.udp_peer[1]}"
    print(f"READY WEB CHAT http://{args.http_bind[0]}:{args.http_bind[1]} UDP peer={peer}",flush=True)
    if args.http_bind[0]=="0.0.0.0":
        addresses=sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET) if not item[4][0].startswith("127.")})
        for address in addresses:print(f"PHONE URL http://{address}:{args.http_bind[1]}/",flush=True)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.shutdown();server.server_close();gateway.close()

if __name__=="__main__":main()
