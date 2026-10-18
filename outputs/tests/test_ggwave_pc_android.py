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


def send_paced(port, line):
    data = (line + "\n").encode("utf-8")
    for offset in range(0, len(data), 32):
        port.write(data[offset:offset + 32])
        time.sleep(0.02)
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
    parser.add_argument("--long", action="store_true")
    parser.add_argument("--android-long", action="store_true")
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.15, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        try:
            send(port, "ggwave on")
            await_line(port, "GGWAVE READY", 15)
            if args.android_long:
                print("Androidでggwaveを開始し、280文字の本文を送信してください。", flush=True)
                deadline = time.monotonic() + 900
                while time.monotonic() < deadline:
                    raw = port.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", "replace").strip()
                    print(f"{port.port}: {line}", flush=True)
                    if line.startswith("GGWAVE RX TEXT: "):
                        received = line[len("GGWAVE RX TEXT: "):]
                        if len(received) != 280:
                            raise RuntimeError(f"Expected 280 characters, received {len(received)}")
                        assert_no_repeat(port, "GGWAVE RX TEXT: ")
                        print("TEST PASS: Android to PC 280-character message received once", flush=True)
                        break
                    if line.startswith("ERROR:"):
                        raise RuntimeError(line)
                else:
                    raise TimeoutError("No 280-character message within 900s")
            elif args.long:
                text = "こんにちは你好" * 40
                print("Androidでggwaveを開始し、受信待機にしてください。PCから280文字を送信します。", flush=True)
                send_paced(port, "ggwave send " + text)
                await_line(port, "GGWAVE MESSAGE QUEUED", 20)
                await_line(port, "GGWAVE MESSAGE SENT", 900)
                print("PCで全片ACK。Androidに280文字が1回だけ表示されたら、Androidから『受信OK』と返信してください。", flush=True)
                await_line(port, "GGWAVE RX TEXT: 受信OK", 120)
                print("TEST PASS: PC to Android 280-character ACK and Android reply", flush=True)
            else:
                print("Androidでggwaveを開始し、『こんにちは』を送信してください。", flush=True)
                await_line(port, "GGWAVE RX TEXT: こんにちは", 90)
                assert_no_repeat(port, "GGWAVE RX TEXT: こんにちは")
                print("PCで受信しました。Androidへ『你好』を送信します。", flush=True)
                send(port, "ggwave send 你好")
                await_line(port, "GGWAVE MESSAGE SENT", 90)
                print("PCの送信完了。Androidのチャット画面で『你好』を確認してください。", flush=True)
            send(port, "ggwave show")
            await_line(port, "GGWAVE MODE=", 5)
        finally:
            send(port, "ggwave off")
            await_line(port, "GGWAVE STOPPED", 5)


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError) as error:
        print(f"TEST FAILED: {error}", file=sys.stderr)
        sys.exit(1)
