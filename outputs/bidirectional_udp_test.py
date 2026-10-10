"""Simultaneously send UDP/IPv4 packets through two acoustic AX.25 endpoints."""
import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import acoustic_ip_endpoint as ip
import acoustic_ping as link

USB_RX = re.compile(rb"^USB_RX SRC=\S+ DEST=\S+ PID=CC HEX=([0-9A-Fa-f]+)$")


def main():
    parser = argparse.ArgumentParser(description="Full-duplex request collision test over half-duplex acoustic AX.25")
    parser.add_argument("--a", default="COM5")
    parser.add_argument("--b", default="COM6")
    parser.add_argument("--rounds", type=int, default=25)
    parser.add_argument("--size", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 8 <= args.size <= 1472:
        parser.error("--size must be 8..1472")
    ports = {
        "A": link.serial.Serial(args.a, 115200, timeout=.02),
        "B": link.serial.Serial(args.b, 115200, timeout=.02),
    }
    readers = {name: link.SerialLines(port) for name, port in ports.items()}
    time.sleep(.5)
    for port in ports.values():
        port.reset_input_buffer()
    results = []
    total_retries = {"A": 0, "B": 0}
    started_all = time.monotonic()
    try:
        for sequence in range(args.rounds):
            payload_a = b"A2B!" + sequence.to_bytes(4, "big") + bytes((sequence + i) & 255 for i in range(args.size - 8))
            payload_b = b"B2A!" + sequence.to_bytes(4, "big") + bytes((255 - sequence - i) & 255 for i in range(args.size - 8))
            packet_a = ip.ipv4_udp("10.23.0.1", "10.23.0.2", 7101, 7102, payload_a, sequence + 1)
            packet_b = ip.ipv4_udp("10.23.0.2", "10.23.0.1", 7102, 7101, payload_b, sequence + 1)
            barrier = threading.Barrier(3)
            def send(name, packet):
                barrier.wait()
                link.send_ipv4(ports[name], packet)
            threads = [threading.Thread(target=send, args=("A", packet_a)), threading.Thread(target=send, args=("B", packet_b))]
            for thread in threads: thread.start()
            round_started = time.monotonic(); barrier.wait()
            for thread in threads: thread.join()
            received = {"A": False, "B": False}; completed = {"A": False, "B": False}; duplicates = {"A": 0, "B": 0}
            retries = {"A": 0, "B": 0}; failed = []
            deadline = round_started + args.timeout
            while time.monotonic() < deadline and not all(received.values()):
                for name, reader in readers.items():
                    for line in reader.poll():
                        if line.startswith(b"RELIABLE RETRY"):
                            retries[name] += 1; total_retries[name] += 1
                        if line.startswith(b"RELIABLE SENT"):
                            completed[name] = True
                        if line.startswith(b"RELIABLE FAILED"):
                            failed.append(name)
                        if line.startswith(b"RELIABLE BUSY"):
                            failed.append(name + "_BUSY")
                        match = USB_RX.match(line)
                        if not match: continue
                        packet = bytes.fromhex(match.group(1).decode("ascii")); udp = ip.parse_udp(packet)
                        expected = payload_b if name == "A" else payload_a
                        if udp and udp["payload"] == expected:
                            if received[name]: duplicates[name] += 1
                            received[name] = True
                time.sleep(.003)
            elapsed = round((time.monotonic() - round_started) * 1000)
            passed = all(received.values()) and not any(duplicates.values()) and not failed
            item = {"sequence": sequence, "pass": passed, "received": received, "tx_completed": completed,
                    "duplicates": duplicates, "retries": retries, "failed": failed, "elapsed_ms": elapsed}
            results.append(item); print(f"round {sequence + 1}/{args.rounds}: {'PASS' if passed else 'FAIL'} {item}", flush=True)
            if not passed: break
            time.sleep(2.0)
    finally:
        for port in ports.values(): port.close()
    passed = len(results) == args.rounds and all(item["pass"] for item in results)
    folder = ROOT / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-bidirectional-udp")
    folder.mkdir(parents=True)
    result = {"pass": passed, "rounds_requested": args.rounds, "rounds_completed": len(results),
              "messages": len(results) * 2, "payload_size": args.size, "total_retries": total_retries,
              "elapsed_ms": round((time.monotonic() - started_all) * 1000), "results": results}
    (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Saved:", folder); print("PASS" if passed else "FAIL", result)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
