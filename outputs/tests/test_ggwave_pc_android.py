"""PC serial endpoint for a manual Android-to-PC-to-Android ggwave test."""
import argparse
import sys
import time

import serial


def await_line(port, marker, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = port.readline()
        if raw:
            line = raw.decode("utf-8", "replace").strip()
            print(f"{port.port}: {line}", flush=True)
            if marker in line:
                return
            if line.startswith("ERROR:") or line.startswith("GGWAVE TX FAILED"):
                raise RuntimeError(line)
    raise TimeoutError(f"No {marker!r} within {timeout}s")


def send(port, line):
    port.write((line + "\n").encode("utf-8"))
    port.flush()


def assert_no_repeat(port, marker, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        raw = port.readline()
        if raw:
            line = raw.decode("utf-8", "replace").strip()
            print(f"{port.port}: {line}", flush=True)
            if marker in line:
                raise RuntimeError(f"Duplicate received: {marker}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="COM5")
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.15, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        try:
            send(port, "ggwave on")
            await_line(port, "GGWAVE READY", 15)
            print("Androidでggwaveを開始し、『こんにちは』を送信してください。", flush=True)
            await_line(port, "GGWAVE RX TEXT: こんにちは", 90)
            assert_no_repeat(port, "GGWAVE RX TEXT: こんにちは")
            print("PCで受信しました。Androidへ『你好』を送信します。", flush=True)
            send(port, "ggwave send 你好")
            await_line(port, "GGWAVE TX DONE", 15)
            print("PCの送信完了。Androidのチャット画面で『你好』を確認してください。", flush=True)
            send(port, "ggwave show")
            await_line(port, "GGWAVE MODE=", 5)
        finally:
            send(port, "ggwave off")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError) as error:
        print(f"TEST FAILED: {error}", file=sys.stderr)
        sys.exit(1)
