"""ATOMs drive Bell 103 connection, DATA, ACK and retries without step commands."""

import argparse
import time

from test_bell103_session_air import serial, send, until


def drain(ports, seconds, done):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for name, port in ports:
            line = port.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            print(f"{name}: {line}", flush=True)
            if "BELL103 AUTO CONNECT TIMEOUT" in line or "BELL103 AUTO DATA RETRIES EXHAUSTED" in line:
                raise RuntimeError(f"{name}: {line}")
            done(name, line)
        if done(None, None):
            return
    raise RuntimeError("timed out waiting for both delivery and ACK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", required=True)
    parser.add_argument("--answerer", required=True)
    args = parser.parse_args()
    if args.caller.upper() == args.answerer.upper():
        raise SystemExit("Use two different COM ports")
    with serial.Serial(args.caller, 115200, timeout=.1, write_timeout=2) as caller, \
         serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
        ports = ((args.caller, caller), (args.answerer, answerer))
        try:
            time.sleep(2)
            caller.reset_input_buffer()
            answerer.reset_input_buffer()
            send(answerer, "bell103 auto answerer")
            send(caller, "bell103 auto caller")
            connected = {args.caller: False, args.answerer: False}

            def on_connect(name, line):
                if name and "BELL103 AUTO RX CONTROL" in line and "state=connected" in line:
                    connected[name] = True
                return all(connected.values())

            drain(ports, 100, on_connect)
            print("CONNECTED: both ATOMs", flush=True)

            for sender_name, sender, receiver_name, message in (
                (args.caller, caller, args.answerer, "AUTO01"),
                (args.answerer, answerer, args.caller, "AUTO02"),
            ):
                delivered = acknowledged = False
                send(sender, f"bell103 data send {message}")

                def on_data(name, line):
                    nonlocal delivered, acknowledged
                    if name == receiver_name and f"BELL103 AUTO RX TEXT len=6: {message}" in line:
                        delivered = True
                    if name == sender_name and "BELL103 AUTO ACK OK" in line:
                        acknowledged = True
                    return delivered and acknowledged

                drain(ports, 180, on_data)
                print(f"PASS: {message} delivered and ACKed", flush=True)
            print("TEST PASS: bidirectional autonomous Bell 103 DATA/ACK", flush=True)
        finally:
            for name, port in ports:
                try:
                    send(port, "bell103 auto stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 18)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
