"""Two-ATOM half-duplex ggwave smoke test. Requires real audio coupling."""
import argparse
import sys
import time

import serial

MESSAGES = ("こんにちは", "你好", "Hello")


def command(port, line):
    port.write((line + "\n").encode("utf-8"))
    port.flush()


def command_paced(port, line):
    data = (line + "\n").encode("utf-8")
    print(f"{port.port}: sending {len(data)} USB bytes in 32-byte chunks", flush=True)
    for offset in range(0, len(data), 32):
        port.write(data[offset:offset + 32])
        time.sleep(0.02)
    port.flush()
    print(f"{port.port}: USB command submitted", flush=True)


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
        if "BOOT DIAG" in line and "name=PANIC" in line:
            raise RuntimeError(f"{port.port}: ATOM restarted after a panic; inspect the lines above")
        if line.startswith("GGWAVE MESSAGE FAILED") or line.startswith("GGWAVE FRAME TX FAILED"):
            raise RuntimeError(f"{port.port}: {line}")
        if marker in line:
            return seen
        if line.startswith("ERROR:") or line.startswith("GGWAVE TX FAILED"):
            raise RuntimeError(f"{port.port}: {line}")
    raise TimeoutError(f"{port.port}: no {marker!r} within {seconds}s")


def assert_no_repeat(port, marker, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        raw = port.readline()
        if raw:
            line = raw.decode("utf-8", "replace").strip()
            print(f"{port.port}: {line}", flush=True)
            if marker in line:
                raise RuntimeError(f"{port.port}: duplicate {marker!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port_a", nargs="?", default="COM5")
    parser.add_argument("port_b", nargs="?", default="COM6")
    parser.add_argument("--long", action="store_true", help="also send a 280-character Japanese message")
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
            if not args.long:
                for index, message in enumerate(MESSAGES):
                    source, target = (a, b) if index % 2 == 0 else (b, a)
                    source.reset_input_buffer()
                    target.reset_input_buffer()
                    command(source, "ggwave send " + message)
                    wait_for(source, "GGWAVE MESSAGE SENT", 150)
                    marker = "GGWAVE RX TEXT: " + message
                    wait_for(target, marker, 5)
                    assert_no_repeat(target, marker)
            else:
                message = "こんにちは你好" * 40  # exactly 280 Unicode characters / 840 UTF-8 bytes
                a.reset_input_buffer()
                b.reset_input_buffer()
                command_paced(a, "ggwave send " + message)
                wait_for(a, "GGWAVE MESSAGE QUEUED", 20)
                wait_for(a, "GGWAVE MESSAGE SENT", 900)
                marker = "GGWAVE RX TEXT: " + message
                wait_for(b, marker, 5)
                assert_no_repeat(b, marker)
            print("TEST PASS: ggwave UTF-8 air link in both directions")
        finally:
            for port in (a, b):
                try:
                    command(port, "ggwave show")
                    wait_for(port, "GGWAVE MODE=", 3)
                except (serial.SerialException, RuntimeError, TimeoutError):
                    pass
                command(port, "ggwave off")
                wait_for(port, "GGWAVE STOPPED", 5)


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError) as exc:
        print(f"TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
