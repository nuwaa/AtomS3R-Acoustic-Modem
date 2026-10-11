"""Ask one ATOM S3R to test both Bell 103 bands and CRC in synthesized PCM."""

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
        device.write(b"bell103 selftest\n")
        until = time.monotonic() + 30
        while time.monotonic() < until:
            line = device.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            print(line, flush=True)
            if "BELL103 SELFTEST PASS both bands CRC OK" in line:
                print("TEST PASS", flush=True)
                return
            if "BELL103 SELFTEST FAILED" in line or "ERROR:" in line:
                break
    raise SystemExit("TEST FAILED")


if __name__ == "__main__":
    main()
