"""Read saved ES8311 settings and acoustic mode from two ATOMs without changing them."""
import argparse
import sys
import time

import serial


def read_settings(port_name):
    with serial.Serial(port_name, 115200, timeout=0.2, write_timeout=2) as port:
        time.sleep(1)
        port.reset_input_buffer()
        for command in (b"audio show\n", b"acoustic show\n"):
            port.write(command)
            port.flush()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                line = port.readline().decode("utf-8", "replace").strip()
                if line:
                    print(f"{port_name}: {line}", flush=True)
                if command.startswith(b"audio") and line.startswith("AUDIO CONFIG"):
                    break
                if command.startswith(b"acoustic") and line.startswith("ACOUSTIC MODE="):
                    break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ports", nargs="*", default=["COM5", "COM6"])
    args = parser.parse_args()
    for port_name in args.ports:
        read_settings(port_name)


if __name__ == "__main__":
    try:
        main()
    except serial.SerialException as error:
        print(f"CHECK FAILED: {error}", file=sys.stderr)
        sys.exit(1)
