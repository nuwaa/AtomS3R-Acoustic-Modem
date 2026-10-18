"""Two-ATOM half-duplex ggwave smoke test. Requires real audio coupling."""
import argparse
import sys
import time

import serial

MESSAGES = ("こんにちは", "你好", "Hello")


def command(port, line):
    port.write((line + "\n").encode("utf-8"))
    port.flush()


def wait_for(port, marker, seconds):
    deadline = time.monotonic() + seconds
    seen = []
    while time.monotonic() < deadline:
        raw = port.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", "replace").strip()
        print(f"{port.port}: {line}", flush=True)
        seen.append(line)
        if marker in line:
            return seen
        if line.startswith("ERROR:") or line.startswith("GGWAVE TX FAILED"):
            raise RuntimeError(f"{port.port}: {line}")
    raise TimeoutError(f"{port.port}: no {marker!r} within {seconds}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port_a", nargs="?", default="COM5")
    parser.add_argument("port_b", nargs="?", default="COM6")
    args = parser.parse_args()
    with serial.Serial(args.port_a, 115200, timeout=0.15, write_timeout=2) as a, \
            serial.Serial(args.port_b, 115200, timeout=0.15, write_timeout=2) as b:
        time.sleep(2)
        a.reset_input_buffer()
        b.reset_input_buffer()
        try:
            for port in (a, b):
                command(port, "ggwave on")
                wait_for(port, "GGWAVE READY", 15)
            for index, message in enumerate(MESSAGES):
                source, target = (a, b) if index % 2 == 0 else (b, a)
                source.reset_input_buffer()
                target.reset_input_buffer()
                command(source, "ggwave send " + message)
                wait_for(source, "GGWAVE TX DONE", 15)
                wait_for(target, "GGWAVE RX TEXT: " + message, 15)
            print("TEST PASS: ggwave UTF-8 air link in both directions")
        finally:
            for port in (a, b):
                command(port, "ggwave off")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError) as exc:
        print(f"TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
