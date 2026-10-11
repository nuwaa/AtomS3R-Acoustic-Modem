"""Two-port, two-direction Bell 103 acoustic smoke test (no Android app)."""

import argparse
import json
import sys
import time
from pathlib import Path

settings = json.loads(Path(__file__).with_name("settings.json").read_text(encoding="utf-8"))
if settings.get("python_libraries"):
    sys.path.insert(0, settings["python_libraries"])
import serial


def run_direction(sender, receiver, sender_name, receiver_name, role, message):
    receiver.reset_input_buffer()
    sender.reset_input_buffer()
    receiver.write(f"bell103 rx {role}\n".encode())
    ready = False
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        line = receiver.readline().decode("utf-8", "replace").strip()
        if line:
            print(f"{receiver_name}: {line}", flush=True)
        if "BELL103 REC 6 seconds" in line:
            ready = True
            break
    if not ready:
        raise RuntimeError(f"{receiver_name} did not start Bell 103 capture")
    send_role = "originate" if role == "answer" else "answer"
    sender.write(f"bell103 tx {send_role} {message}\n".encode())
    received_crc = received_text = False
    deadline = time.monotonic() + 22
    while time.monotonic() < deadline:
        for name, port in ((sender_name, sender), (receiver_name, receiver)):
            line = port.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            print(f"{name}: {line}", flush=True)
            if name == receiver_name and "BELL103 RX CRC OK" in line:
                received_crc = True
            if name == receiver_name and f"BELL103 TEXT: {message}" in line:
                received_text = True
            if name == receiver_name and "BELL103 RX NO VALID FRAME" in line:
                raise RuntimeError(f"{receiver_name} did not decode {message}")
        if received_crc and received_text:
            return
    raise RuntimeError(f"{receiver_name} timed out waiting for {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--originator", required=True)
    parser.add_argument("--answerer", required=True)
    args = parser.parse_args()
    if args.originator.upper() == args.answerer.upper():
        raise SystemExit("Use two different COM ports")
    with serial.Serial(args.originator, 115200, timeout=.1, write_timeout=2) as originator, \
         serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
        time.sleep(2)
        run_direction(originator, answerer, args.originator, args.answerer, "answer", "AIR01")
        time.sleep(1)
        run_direction(answerer, originator, args.answerer, args.originator, "originate", "AIR02")
    print("TEST PASS: Bell 103 air link, both bands and both directions", flush=True)


if __name__ == "__main__":
    main()
