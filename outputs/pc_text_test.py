"""Verify PC-A USB -> acoustic AX.25 -> USB PC-B in both directions."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial

RX = re.compile(r"^USB_RX SRC=(\S+) DEST=(\S+) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]+)$")


def paced_write(port, command):
    for offset in range(0, len(command), 32):
        port.write(command[offset:offset + 32]);port.flush();time.sleep(0.01)


def trial(sender, receiver, payload, label, pid="F0"):
    encoded = payload.encode("utf-8") if isinstance(payload, str) else payload
    sender.reset_input_buffer()
    receiver.reset_input_buffer()
    command = "u " if pid.upper() == "F0" else f"x {pid.upper()} "
    sender.write((command + encoded.hex() + "\n").encode("ascii"))
    sent = received = False
    log = []
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        for port, side in ((sender, "TX"), (receiver, "RX")):
            line = port.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            print(label, side, line, flush=True)
            log.append((side, line))
            sent |= side == "TX" and line.startswith("TX OK")
            match = RX.match(line) if side == "RX" else None
            received |= bool(match and match.group(3).upper() == pid.upper() and bytes.fromhex(match.group(4)) == encoded)
        if sent and received:
            return True, log
    return False, log


def reliable_trial(sender, receiver, payload, label):
    encoded = payload.encode("utf-8") if isinstance(payload, str) else payload
    sender.reset_input_buffer(); receiver.reset_input_buffer()
    paced_write(sender, ("z " + encoded.hex() + "\n").encode("ascii"))
    sent = received = False; log = []; deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        for port, side in ((sender, "TX"), (receiver, "RX")):
            line = port.readline().decode("utf-8", errors="replace").strip()
            if not line: continue
            print(label, side, line, flush=True); log.append((side, line))
            sent |= side == "TX" and line.startswith("RELIABLE SENT")
            match = RX.match(line) if side == "RX" else None
            received |= bool(match and match.group(3).upper() == "F0" and bytes.fromhex(match.group(4)) == encoded)
        if sent and received: return True, log
    return False, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", default="COM5")
    parser.add_argument("--b", default="COM6")
    args = parser.parse_args()
    folder = ROOT / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-pc-usb-text")
    folder.mkdir(parents=True)
    a = serial.Serial(args.a, 115200, timeout=0.05)
    b = serial.Serial(args.b, 115200, timeout=0.05)
    time.sleep(0.5)
    try:
        ab, ablog = trial(a, b, "PC-AからPC-Bへ", "A_TO_B")
        time.sleep(0.8)
        ba, balog = trial(b, a, "PC-BからPC-Aへ", "B_TO_A")
        time.sleep(0.8)
        generic, genericlog = trial(a, b, bytes.fromhex("450000140001000040010000C0000201C6336402"), "PID_CC", "CC")
        time.sleep(0.8)
        long_text = ("長文転送テスト:0123456789/" * 10).encode("utf-8")
        reliable_ab, reliable_ab_log = reliable_trial(a, b, long_text, "RELIABLE_A_TO_B")
        time.sleep(0.8)
        binary = (bytes(range(256)) * 5)[:1100]
        reliable_ba, reliable_ba_log = reliable_trial(b, a, binary, "RELIABLE_B_TO_A")
    finally:
        a.close()
        b.close()
    result = {"A_to_B": ab, "B_to_A": ba, "PID_CC_binary": generic,
              "reliable_long_text_A_to_B": reliable_ab, "reliable_binary_B_to_A": reliable_ba,
              "port_A": args.a, "port_B": args.b}
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "logs.json").write_text(json.dumps({"A_to_B": ablog, "B_to_A": balog, "PID_CC": genericlog,
        "reliable_A_to_B": reliable_ab_log, "reliable_B_to_A": reliable_ba_log}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", folder)
    passed=ab and ba and generic and reliable_ab and reliable_ba
    print("PASS" if passed else "FAIL", result)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
