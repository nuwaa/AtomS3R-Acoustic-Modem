"""Run the Bell 103 sound-only diagnostic on one connected ATOM S3R."""

import argparse
import json
import sys
import time
from pathlib import Path

SETTINGS = Path(__file__).with_name("settings.json")
settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
if settings.get("python_libraries"):
    sys.path.insert(0, settings["python_libraries"])

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=2) as device:
        time.sleep(2)
        device.reset_input_buffer()
        device.write(b"acoustic show\n")
        time.sleep(0.3)
        device.write(b"bell103 tone\n")
        deadline = time.monotonic() + 22
        saw_start = saw_end = saw_rx = False
        while time.monotonic() < deadline:
            line = device.readline().decode("utf-8", "replace").strip()
            if not line:
                continue
            print(line, flush=True)
            if "BELL103 OVERTURE DEMO" in line:
                saw_start = True
            if "BELL103 OVERTURE OK samples=537200" in line:
                saw_end = True
            if saw_end and "STATE RX LISTEN" in line:
                saw_rx = True
                break
        if not (saw_start and saw_end and saw_rx):
            raise SystemExit("TEST FAILED: overture did not finish and return to RX")
        print("TEST PASS: sound demo completed; AX.25 RX resumed", flush=True)


if __name__ == "__main__":
    main()
