"""User-space IPv4/ICMP endpoint over USB CDC -> reliable acoustic AX.25 PID CC."""
import argparse
import ipaddress
import json
import os
import re
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial

USB_RX = re.compile(rb"^USB_RX SRC=\S+ DEST=\S+ PID=CC HEX=([0-9A-Fa-f]+)$")


def checksum(data):
    if len(data) & 1:
        data += b"\0"
    total = sum(struct.unpack(f"!{len(data)//2}H", data))
    total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def ipv4_icmp(source, destination, icmp_type, identifier, sequence, payload):
    source_bytes = ipaddress.IPv4Address(source).packed
    destination_bytes = ipaddress.IPv4Address(destination).packed
    icmp = struct.pack("!BBHHH", icmp_type, 0, 0, identifier, sequence) + payload
    icmp = struct.pack("!BBHHH", icmp_type, 0, checksum(icmp), identifier, sequence) + payload
    total_length = 20 + len(icmp)
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total_length, sequence, 0, 64, 1, 0,
                         source_bytes, destination_bytes)
    header = header[:10] + struct.pack("!H", checksum(header)) + header[12:]
    return header + icmp


def parse_icmp(packet):
    if len(packet) < 28 or packet[0] >> 4 != 4:
        return None
    header_length = (packet[0] & 15) * 4
    total = struct.unpack("!H", packet[2:4])[0]
    if header_length < 20 or total > len(packet) or packet[9] != 1 or checksum(packet[:header_length]):
        return None
    icmp = packet[header_length:total]
    if len(icmp) < 8 or checksum(icmp):
        return None
    kind, code, _, identifier, sequence = struct.unpack("!BBHHH", icmp[:8])
    return {"type": kind, "code": code, "id": identifier, "sequence": sequence,
            "source": str(ipaddress.IPv4Address(packet[12:16])),
            "destination": str(ipaddress.IPv4Address(packet[16:20])), "payload": icmp[8:]}


def paced_command(port, command):
    for offset in range(0, len(command), 32):
        port.write(command[offset:offset + 32]); port.flush(); time.sleep(0.01)


def send_ipv4(port, packet):
    if not 20 <= len(packet) <= 1500:
        raise ValueError("IPv4 packet must be 20..1500 bytes")
    paced_command(port, ("y " + packet.hex() + "\n").encode("ascii"))


class SerialLines:
    def __init__(self, port):
        self.port = port
        self.buffer = bytearray()

    def poll(self):
        data = self.port.read(max(1, self.port.in_waiting))
        if data:
            self.buffer.extend(data)
        lines = []
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            lines.append(line.strip())
        return lines


def packets(lines):
    for line in lines:
        match = USB_RX.match(line)
        if match:
            yield bytes.fromhex(match.group(1).decode("ascii"))


def listen(port, local_ip):
    reader = SerialLines(port)
    print(f"ICMP endpoint {local_ip} listening on {port.port}")
    while True:
        for packet in packets(reader.poll()):
            parsed = parse_icmp(packet)
            if parsed and parsed["type"] == 8 and parsed["destination"] == local_ip:
                reply = ipv4_icmp(local_ip, parsed["source"], 0, parsed["id"], parsed["sequence"], parsed["payload"])
                send_ipv4(port, reply)
                print(f"echo reply -> {parsed['source']} seq={parsed['sequence']}", flush=True)
        time.sleep(0.01)


def ping(port, local_ip, remote_ip, count, timeout, size):
    reader = SerialLines(port); identifier = os.getpid() & 0xffff
    failures = 0
    for sequence in range(1, count + 1):
        payload = bytes((index & 0xff for index in range(size)))
        request = ipv4_icmp(local_ip, remote_ip, 8, identifier, sequence, payload)
        started = time.monotonic(); send_ipv4(port, request); deadline = started + timeout; found = False
        while time.monotonic() < deadline:
            for packet in packets(reader.poll()):
                parsed = parse_icmp(packet)
                if parsed and parsed["type"] == 0 and parsed["source"] == remote_ip and parsed["destination"] == local_ip and parsed["id"] == identifier and parsed["sequence"] == sequence and parsed["payload"] == payload:
                    elapsed = (time.monotonic() - started) * 1000
                    print(f"Reply from {remote_ip}: bytes={len(payload)} seq={sequence} time={elapsed:.0f}ms")
                    found = True; break
            if found: break
            time.sleep(0.01)
        if not found:
            failures += 1; print(f"Request timed out: seq={sequence}")
    return failures == 0


def main():
    parser = argparse.ArgumentParser(description="IPv4 ICMP over reliable acoustic AX.25")
    parser.add_argument("--port", required=True)
    parser.add_argument("--local-ip", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--listen", action="store_true")
    mode.add_argument("--ping", metavar="IP")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--size", type=int, default=32)
    args = parser.parse_args()
    port = serial.Serial(args.port, 115200, timeout=0.05); time.sleep(0.4); port.reset_input_buffer()
    try:
        if args.listen: listen(port, args.local_ip)
        else: raise SystemExit(0 if ping(port, args.local_ip, args.ping, args.count, args.timeout, args.size) else 1)
    except KeyboardInterrupt:
        pass
    finally:
        port.close()


if __name__ == "__main__":
    main()
