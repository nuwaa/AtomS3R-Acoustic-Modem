"""User-space remote IPv4 endpoint: ICMP Echo and UDP Echo over acoustic AX.25."""
import argparse
import hashlib
import ipaddress
import json
import struct
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import acoustic_ping as link

FILE_MAGIC=b"AUF1"


class FileReceiver:
    def __init__(self,directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True);self.current=None
    def handle(self,payload):
        if len(payload)<9 or payload[:4]!=FILE_MAGIC:return None
        kind=payload[4:5];transfer_id=struct.unpack("!I",payload[5:9])[0]
        if kind==b"S" and len(payload)>=45:
            size=struct.unpack("!I",payload[9:13])[0];digest=payload[13:45];name=Path(payload[45:].decode("utf-8","replace")).name or "received.bin"
            if size>65535:return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,0,2)
            self.current={"id":transfer_id,"size":size,"digest":digest,"name":name,"data":bytearray()}
            return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,0,0)
        if kind!=b"D" or len(payload)<13 or not self.current or self.current["id"]!=transfer_id:return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,0,2)
        offset=struct.unpack("!I",payload[9:13])[0];data=payload[13:];current=self.current
        if offset==len(current["data"]):current["data"].extend(data)
        elif offset>len(current["data"]):return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,len(current["data"]),2)
        next_offset=len(current["data"])
        if next_offset>current["size"]:return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,next_offset,2)
        if next_offset==current["size"]:
            digest=hashlib.sha256(current["data"]).digest();status=1 if digest==current["digest"] else 2
            if status==1:(self.directory/current["name"]).write_bytes(current["data"])
            return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,next_offset,status)+digest
        return FILE_MAGIC+b"A"+struct.pack("!IIB",transfer_id,next_offset,0)


def udp_checksum(source,destination,udp):
    pseudo=ipaddress.IPv4Address(source).packed+ipaddress.IPv4Address(destination).packed+struct.pack("!BBH",0,17,len(udp))
    return link.checksum(pseudo+udp)


def ipv4_udp(source,destination,source_port,destination_port,payload,identification=1):
    length=8+len(payload);udp=struct.pack("!HHHH",source_port,destination_port,length,0)+payload
    value=udp_checksum(source,destination,udp);value=value or 0xffff
    udp=struct.pack("!HHHH",source_port,destination_port,length,value)+payload
    source_bytes=ipaddress.IPv4Address(source).packed;destination_bytes=ipaddress.IPv4Address(destination).packed;total=20+length
    header=struct.pack("!BBHHHBBH4s4s",0x45,0,total,identification,0,64,17,0,source_bytes,destination_bytes)
    header=header[:10]+struct.pack("!H",link.checksum(header))+header[12:]
    return header+udp


def parse_udp(packet):
    if len(packet)<28 or packet[0]>>4!=4:return None
    ihl=(packet[0]&15)*4;total=struct.unpack("!H",packet[2:4])[0]
    if ihl<20 or total>len(packet) or packet[9]!=17 or link.checksum(packet[:ihl]):return None
    udp=packet[ihl:total];source_port,destination_port,length,check=struct.unpack("!HHHH",udp[:8])
    if length<8 or length!=len(udp):return None
    source=str(ipaddress.IPv4Address(packet[12:16]));destination=str(ipaddress.IPv4Address(packet[16:20]))
    if check and udp_checksum(source,destination,udp):return None
    return {"source":source,"destination":destination,"source_port":source_port,"destination_port":destination_port,"payload":udp[8:]}


def run_endpoint(args,file_receiver):
    serial=link.serial.Serial(args.port,115200,timeout=.05);time.sleep(.4);serial.reset_input_buffer();reader=link.SerialLines(serial)
    print(f"READY IPv4 endpoint {args.local_ip}; ICMP echo; UDP echo port {args.udp_port}; {args.port}",flush=True)
    try:
        while True:
            for packet in link.packets(reader.poll()):
                icmp=link.parse_icmp(packet)
                if icmp and icmp["type"]==8 and icmp["destination"]==args.local_ip:
                    reply=link.ipv4_icmp(args.local_ip,icmp["source"],0,icmp["id"],icmp["sequence"],icmp["payload"])
                    link.send_ipv4(serial,reply);print(f"ICMP echo {len(icmp['payload'])} bytes -> {icmp['source']}",flush=True);continue
                udp=parse_udp(packet)
                if udp and udp["destination"]==args.local_ip and udp["destination_port"]==args.udp_port:
                    response=file_receiver.handle(udp["payload"])
                    if response is None:response=udp["payload"]
                    reply=ipv4_udp(args.local_ip,udp["source"],args.udp_port,udp["source_port"],response)
                    link.send_ipv4(serial,reply);print(f"UDP reply {len(response)} bytes -> {udp['source']}:{udp['source_port']}",flush=True)
            time.sleep(.005)
    finally:serial.close()


def main():
    parser=argparse.ArgumentParser(description="Remote ICMP and UDP echo endpoint over acoustic IPv4")
    parser.add_argument("--port",default="COM6");parser.add_argument("--local-ip",default="10.23.0.2");parser.add_argument("--udp-port",type=int,default=7000)
    parser.add_argument("--receive-dir",default=str(ROOT/"received_files"));parser.add_argument("--reconnect-delay",type=float,default=2)
    parser.add_argument("--no-auto-reconnect",action="store_true");args=parser.parse_args();file_receiver=FileReceiver(args.receive_dir);attempt=0
    while True:
        try:run_endpoint(args,file_receiver);break
        except KeyboardInterrupt:break
        except (link.serial.SerialException,OSError) as error:
            if args.no_auto_reconnect:raise
            attempt+=1;print(f"ENDPOINT RECONNECT attempt={attempt} port={args.port} in {args.reconnect_delay:g}s: {error}",flush=True);time.sleep(args.reconnect_delay)


if __name__=="__main__":main()
