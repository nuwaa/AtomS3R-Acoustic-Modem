"""USB CDC console <-> acoustic AX.25 text bridge client."""
import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial

RX = re.compile(r"^USB_RX SRC=(\S+) DEST=(\S+) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]*)$")


def write_command(port, command):
    # HWCDC has a small receive ring; pace long hexadecimal commands.
    for offset in range(0, len(command), 32):
        port.write(command[offset:offset + 32])
        port.flush()
        time.sleep(0.01)


def reader(port, stop):
    while not stop.is_set():
        line = port.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue
        match = RX.match(line)
        if match:
            source, destination, pid, encoded = match.groups()
            payload = bytes.fromhex(encoded)
            text = payload.decode("utf-8", errors="replace")
            print(f"\n[{source}>{destination} PID={pid}] {text}", flush=True)
        elif line.startswith(("TX ", "STATE ", "ERROR:", "RELIABLE ")):
            print(f"\n<{line}>", flush=True)


def send(port, message):
    payload = message.encode("utf-8")
    if not 1 <= len(payload) <= 1500:
        raise ValueError("payload must be 1..1500 bytes")
    write_command(port, f"z {payload.hex()}\n".encode("ascii"))


def main():
    parser = argparse.ArgumentParser(description="PC text over USB CDC and acoustic AX.25")
    parser.add_argument("--port", default=CFG["port"])
    parser.add_argument("--send", metavar="TEXT", help="send once; omit for interactive chat")
    parser.add_argument("--file", type=Path, help="send one binary file (maximum 1500 bytes)")
    parser.add_argument("--listen-seconds", type=float, default=3.0)
    args = parser.parse_args()
    device = serial.Serial(args.port, 115200, timeout=0.1)
    time.sleep(0.4)
    device.reset_input_buffer()
    stop = threading.Event()
    thread = threading.Thread(target=reader, args=(device, stop), daemon=True)
    thread.start()
    try:
        if args.file is not None:
            payload=args.file.read_bytes()
            if not 1 <= len(payload) <= 1500:
                raise ValueError("file must be 1..1500 bytes")
            write_command(device, f"z {payload.hex()}\n".encode("ascii"))
            time.sleep(args.listen_seconds)
            return
        if args.send is not None:
            send(device, args.send)
            time.sleep(args.listen_seconds)
            return
        print(f"Connected to {args.port}. Type a message and press Enter; Ctrl+C exits.")
        while True:
            message = input("> ")
            if message:
                send(device, message)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop.set()
        thread.join(timeout=0.3)
        device.close()


if __name__ == "__main__":
    main()
