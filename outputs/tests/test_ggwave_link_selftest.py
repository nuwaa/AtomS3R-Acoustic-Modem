"""Exercise the actual ESP32 ggwave fragmentation/ACK state machine without audio."""
import argparse
import sys
import time

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="COM5")
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.2, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        port.write(b"ggwave link selftest\n")
        port.flush()
        end = time.monotonic() + 15
        while time.monotonic() < end:
            line = port.readline().decode("utf-8", "replace").strip()
            if line:
                print(f"{args.port}: {line}", flush=True)
            if "GGWAVE LINK SELFTEST PASS" in line:
                print("TEST PASS: 280-character UTF-8 framing, dropped ACK recovery, exactly one delivery")
                return
            if "GGWAVE LINK SELFTEST FAIL" in line:
                raise RuntimeError("ATOM reported link self-test failure")
        raise TimeoutError("no ggwave link self-test result within 15s")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError) as error:
        print(f"TEST FAILED: {error}", file=sys.stderr)
        sys.exit(1)
