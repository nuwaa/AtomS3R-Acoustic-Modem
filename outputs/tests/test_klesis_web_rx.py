"""Manual Klesis browser -> ATOM official variable-length ggwave air test."""
import argparse
import sys
import time

import serial


def wait_for(port, expected, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = port.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", "replace").strip()
        print(f"{port.port}: {line}", flush=True)
        if "Guru Meditation" in line or "BOOT DIAG reset_reason=4" in line:
            raise RuntimeError("ATOM restarted during web receive")
        if line.startswith("ERROR: ggwave") or line.startswith("GGWAVE WEB RX FAILED"):
            raise RuntimeError(line)
        if expected in line:
            return line
    raise TimeoutError(f"No {expected!r} within {timeout}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="COM5")
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.15, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        try:
            port.write(b"ggwave web on\n")
            wait_for(port, "GGWAVE WEB READY", 30)
            for message in ("こんにちは", "你好", "Hello"):
                print(f"Klesis (https://nolimitwaiz.github.io/klesis/) をNormalにし、{message!r} を1回送ってください。", flush=True)
                wait_for(port, "GGWAVE WEB RX TEXT: " + message, 120)
            print("Klesisから '一行目\\n二行目' を改行入りで1回送ってください。", flush=True)
            wait_for(port, "GGWAVE WEB RX TEXT: 一行目", 120)
            wait_for(port, "二行目", 5)
            print("ATOM画面が一行目・二行目の2行表示になっていることを確認してください。", flush=True)
            print("TEST PASS: Klesis decoded UTF-8 text including a line break", flush=True)
            port.write(b"ggwave show\n")
            wait_for(port, "GGWAVE MODE=web", 5)
        finally:
            port.write(b"ggwave web off\n")
            wait_for(port, "GGWAVE STOPPED", 10)


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, TimeoutError, RuntimeError) as error:
        print(f"TEST FAILED: {error}", file=sys.stderr)
        sys.exit(1)
