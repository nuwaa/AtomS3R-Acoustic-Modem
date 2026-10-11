"""Start both ATOMs once; firmware drives the Bell 103 handshake itself."""

import argparse
import time

from test_bell103_session_air import serial, send, until


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
            send(answerer, "bell103 auto answerer")
            send(caller, "bell103 auto caller")
            connected = {args.caller: False, args.answerer: False}
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and not all(connected.values()):
                for name, port in ((args.caller, caller), (args.answerer, answerer)):
                    line = port.readline().decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    print(f"{name}: {line}", flush=True)
                    if "BELL103 AUTO CONNECT TIMEOUT" in line or "BELL103 AUTO TX CONTROL FAILED" in line:
                        raise RuntimeError(f"{name}: {line}")
                    if "BELL103 AUTO RX CONTROL" in line and "state=connected" in line:
                        connected[name] = True
            if not all(connected.values()):
                raise RuntimeError(f"connection timeout: {connected}")
            print("TEST PASS: both ATOMs connected without TX/RX step commands", flush=True)
        finally:
            for name, port in ((args.caller, caller), (args.answerer, answerer)):
                try:
                    send(port, "bell103 auto stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 18)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
