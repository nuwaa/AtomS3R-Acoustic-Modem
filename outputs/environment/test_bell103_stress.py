"""Repeated autonomous Bell 103 DATA/ACK air test with duplicate detection."""

import argparse
import time
from collections import Counter

from test_bell103_session_air import serial, send, until


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", required=True)
    parser.add_argument("--answerer", required=True)
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    if args.caller.upper() == args.answerer.upper() or not 2 <= args.count <= 20:
        raise SystemExit("Use distinct COM ports and count 2..20")

    names = (args.caller, args.answerer)
    messages = [f"STRESS{i:02d}" for i in range(1, args.count + 1)]
    deliveries = Counter()
    acks = Counter()
    connected = set()
    overture = ready = hello = False
    with serial.Serial(args.caller, 115200, timeout=.1, write_timeout=2) as caller, \
         serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
        ports = ((args.caller, caller), (args.answerer, answerer))

        def poll(deadline, done, allow_timeout=False):
            nonlocal overture, ready, hello
            while time.monotonic() < deadline:
                for name, port in ports:
                    line = port.readline().decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    print(f"{name}: {line}", flush=True)
                    if "BELL103 AUTO CONNECT TIMEOUT" in line or "BELL103 AUTO DATA RETRIES EXHAUSTED" in line or "BELL103 AUTO TX CONTROL FAILED" in line:
                        raise RuntimeError(f"{name}: {line}")
                    if name == args.answerer and "BELL103 AUTO RX READY" in line:
                        ready = True
                    if name == args.caller and "BELL103 OVERTURE OK" in line:
                        overture = True
                    if name == args.caller and "BELL103 AUTO TX CONTROL type=1" in line:
                        if not overture:
                            raise RuntimeError("HELLO preceded overture")
                        hello = True
                    if "BELL103 AUTO RX CONTROL" in line and "state=connected" in line:
                        connected.add(name)
                    if "BELL103 AUTO RX TEXT" in line:
                        for message in messages:
                            if line.endswith(": " + message):
                                deliveries[(name, message)] += 1
                    if "BELL103 AUTO ACK OK" in line:
                        acks[name] += 1
                if done():
                    return
            if not allow_timeout:
                raise RuntimeError("timed out waiting for Bell 103 progress")

        try:
            time.sleep(2)
            caller.reset_input_buffer()
            answerer.reset_input_buffer()
            send(answerer, "bell103 auto answerer")
            send(caller, "bell103 auto caller")
            poll(time.monotonic() + 110, lambda: len(connected) == 2 and ready and hello)
            for index, message in enumerate(messages):
                sender_name, sender = ports[index % 2]
                receiver_name, _ = ports[(index + 1) % 2]
                before_acks = acks[sender_name]
                send(sender, f"bell103 data send {message}")
                poll(time.monotonic() + 180,
                     lambda: deliveries[(receiver_name, message)] >= 1 and acks[sender_name] > before_acks)
                print(f"PASS: {message} delivered and ACKed", flush=True)
            poll(time.monotonic() + 20, lambda: False, allow_timeout=True)
        finally:
            for name, port in ports:
                try:
                    send(port, "bell103 auto stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 18)
                except (OSError, RuntimeError) as error:
                    print(f"WARNING: {name} cleanup: {error}", flush=True)

        for index, message in enumerate(messages):
            receiver_name = names[(index + 1) % 2]
            if deliveries[(receiver_name, message)] != 1:
                raise RuntimeError(f"{message}: expected one delivery, got {deliveries[(receiver_name, message)]}")
        print(f"TEST PASS: {len(messages)} alternating Bell 103 messages, ACKs, no duplicate delivery", flush=True)


if __name__ == "__main__":
    main()
