"""Verify a maximum-size 1500-byte IPv4 UDP datagram in both directions."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import acoustic_ip_endpoint as ip
import acoustic_ping as link

USB_RX = re.compile(rb"^USB_RX SRC=\S+ DEST=\S+ PID=CC HEX=([0-9A-Fa-f]+)$")


def transfer(sender_name, receiver_name, ports, readers, packet, expected, timeout):
    for port in ports.values(): port.reset_input_buffer()
    started = time.monotonic(); link.send_ipv4(ports[sender_name], packet)
    sent = False; received = False; retries = 0; duplicates = 0; failed = []
    deadline = started + timeout
    while time.monotonic() < deadline and not (sent and received):
        for name, reader in readers.items():
            for line in reader.poll():
                if name == sender_name and line.startswith(b"RELIABLE RETRY"): retries += 1
                if name == sender_name and line.startswith(b"RELIABLE SENT"): sent = True
                if name == sender_name and line.startswith((b"RELIABLE FAILED", b"RELIABLE BUSY")): failed.append(line.decode("ascii", "replace"))
                match = USB_RX.match(line)
                if name != receiver_name or not match: continue
                raw = bytes.fromhex(match.group(1).decode("ascii")); udp = ip.parse_udp(raw)
                if udp and udp["payload"] == expected:
                    if received: duplicates += 1
                    received = True
        time.sleep(.003)
    elapsed = round((time.monotonic() - started) * 1000)
    return {"pass": sent and received and not failed and not duplicates, "sender": sender_name,
            "receiver": receiver_name, "sent_complete": sent, "received_exact": received,
            "retries": retries, "duplicates": duplicates, "failed": failed, "elapsed_ms": elapsed}


def main():
    parser = argparse.ArgumentParser(description="1500-byte IPv4 / 1472-byte UDP payload acoustic MTU test")
    parser.add_argument("--a", default="COM5"); parser.add_argument("--b", default="COM6")
    parser.add_argument("--timeout", type=float, default=240); args = parser.parse_args()
    size = 1472
    payload_a = b"MTU-A2B!" + bytes(i & 255 for i in range(size - 8))
    payload_b = b"MTU-B2A!" + bytes((255 - i) & 255 for i in range(size - 8))
    packet_a = ip.ipv4_udp("10.23.0.1", "10.23.0.2", 7201, 7202, payload_a, 0x1500)
    packet_b = ip.ipv4_udp("10.23.0.2", "10.23.0.1", 7202, 7201, payload_b, 0x1501)
    assert len(packet_a) == len(packet_b) == 1500
    ports = {"A": link.serial.Serial(args.a, 115200, timeout=.02), "B": link.serial.Serial(args.b, 115200, timeout=.02)}
    readers = {name: link.SerialLines(port) for name, port in ports.items()}; time.sleep(.5)
    started = time.monotonic(); results = []
    try:
        results.append(transfer("A", "B", ports, readers, packet_a, payload_a, args.timeout)); print(results[-1], flush=True)
        time.sleep(2)
        results.append(transfer("B", "A", ports, readers, packet_b, payload_b, args.timeout)); print(results[-1], flush=True)
    finally:
        for port in ports.values(): port.close()
    passed = all(item["pass"] for item in results)
    folder = ROOT / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-mtu-udp"); folder.mkdir(parents=True)
    result = {"pass": passed, "ipv4_bytes": 1500, "udp_payload_bytes": size, "reliable_fragments": 24,
              "elapsed_ms": round((time.monotonic() - started) * 1000), "directions": results}
    (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Saved:", folder); print("PASS" if passed else "FAIL", result)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__": main()
