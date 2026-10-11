"""Four-way Bell 103 control handshake over the two ATOM acoustic links."""

import argparse
import json
import sys
import time
from pathlib import Path

settings = json.loads(Path(__file__).with_name("settings.json").read_text(encoding="utf-8"))
if settings.get("python_libraries"):
    sys.path.insert(0, settings["python_libraries"])
import serial


def send(port, command):
    port.write((command + "\n").encode("ascii"))


def until(port, label, fragment, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line:
            print(f"{label}: {line}", flush=True)
        if "ERROR:" in line or "FAILED" in line or "NO VALID" in line:
            raise RuntimeError(f"{label}: {line}")
        if fragment in line:
            return line
    raise RuntimeError(f"{label}: timeout waiting for {fragment}")


def step(sender, receiver, sender_name, receiver_name, message, expected_state):
    receiver.reset_input_buffer()
    sender.reset_input_buffer()
    send(receiver, "bell103 session rx")
    until(receiver, receiver_name, "BELL103 REC 6 seconds", 6)
    send(sender, "bell103 session tx")
    until(sender, sender_name, f"BELL103 SESSION TX type={message}", 12)
    received = until(receiver, receiver_name, f"BELL103 SESSION RX type={message}", 25)
    if f"state={expected_state}" not in received:
        raise RuntimeError(f"{receiver_name}: unexpected state after type {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", required=True)
    parser.add_argument("--answerer", required=True)
    args = parser.parse_args()
    if args.caller.upper() == args.answerer.upper():
        raise SystemExit("Use two different COM ports")
    with serial.Serial(args.caller, 115200, timeout=.1, write_timeout=2) as caller, \
         serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
        try:
            time.sleep(2)
            caller.reset_input_buffer()
            answerer.reset_input_buffer()
            send(caller, "bell103 session caller")
            send(answerer, "bell103 session answerer")
            until(caller, args.caller, "BELL103 SESSION START role=caller", 5)
            until(answerer, args.answerer, "BELL103 SESSION START role=answerer", 5)
            step(caller, answerer, args.caller, args.answerer, 1, "wait-confirm")
            step(answerer, caller, args.answerer, args.caller, 2, "wait-established")
            step(caller, answerer, args.caller, args.answerer, 3, "connected")
            step(answerer, caller, args.answerer, args.caller, 4, "connected")
            print("TEST PASS: both ATOMs confirmed Bell 103 session over air", flush=True)
        finally:
            for name, port in ((args.caller, caller), (args.answerer, answerer)):
                try:
                    send(port, "bell103 session stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 5)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
