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
            answerer_ready = overture_done = hello_after_overture = False
            deadline = time.monotonic() + 110
            while time.monotonic() < deadline and not all(connected.values()):
                for name, port in ((args.caller, caller), (args.answerer, answerer)):
                    line = port.readline().decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    print(f"{name}: {line}", flush=True)
                    if name == args.answerer and "BELL103 AUTO RX READY" in line:
                        answerer_ready = True
                    if name == args.caller and "BELL103 OVERTURE OK" in line and "HELLO follows silence" in line:
                        overture_done = True
                    if name == args.caller and "BELL103 AUTO TX CONTROL type=1" in line:
                        if not overture_done:
                            raise RuntimeError("caller sent HELLO before overture boundary")
                        hello_after_overture = True
                    if "BELL103 AUTO CONNECT TIMEOUT" in line or "BELL103 AUTO TX CONTROL FAILED" in line:
                        raise RuntimeError(f"{name}: {line}")
                    if "BELL103 AUTO RX CONTROL" in line and "state=connected" in line:
                        connected[name] = True
            if not all(connected.values()) or not answerer_ready or not hello_after_overture:
                raise RuntimeError(f"connection/boundary failed: connected={connected}, answerer_ready={answerer_ready}, overture_hello={hello_after_overture}")
            print("TEST PASS: overture boundary and autonomous Bell 103 connection", flush=True)
        finally:
            for name, port in ((args.caller, caller), (args.answerer, answerer)):
                try:
                    send(port, "bell103 auto stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 18)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
