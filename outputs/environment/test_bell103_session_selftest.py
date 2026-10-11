"""Run the Bell 103 control-protocol self-test on one ATOM."""

import argparse
import json
import sys
import time
from pathlib import Path

settings = json.loads(Path(__file__).with_name("settings.json").read_text(encoding="utf-8"))
if settings.get("python_libraries"):
    sys.path.insert(0, settings["python_libraries"])
import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=.25, write_timeout=2) as device:
        time.sleep(2)
        device.reset_input_buffer()
        device.write(b"bell103 session selftest\n")
        until = time.monotonic() + 10
        while time.monotonic() < until:
            line = device.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            print(line, flush=True)
            if "BELL103 SESSION SELFTEST PASS" in line:
                print("TEST PASS", flush=True)
                return
            if "BELL103 SESSION SELFTEST FAILED" in line or "ERROR:" in line:
                break
    raise SystemExit("TEST FAILED")


if __name__ == "__main__":
    main()
