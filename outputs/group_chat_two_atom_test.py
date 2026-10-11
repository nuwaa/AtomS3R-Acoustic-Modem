"""Two-ATOM bench check for optional acoustic group chat (no firmware flashing)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment" / "settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial


class Atom:
    def __init__(self, port: str):
        self.port = port
        self.device = serial.Serial(port, 115200, timeout=0.15)
        self.lines: list[str] = []

    def send(self, command: str):
        self.device.write(command.encode("utf-8"))
        self.device.flush()

    def poll(self):
        while self.device.in_waiting:
            line = self.device.readline().decode("utf-8", errors="replace").strip()
            if line:
                self.lines.append(line)
                print(f"{self.port}: {line}", flush=True)

    def close(self):
        self.device.close()


def until(atoms: list[Atom], predicate, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for atom in atoms:
            atom.poll()
        if predicate():
            return True
        time.sleep(0.05)
    for atom in atoms:
        atom.poll()
    return predicate()


def received(atom: Atom, source: str, text: str, start: int) -> bool:
    pattern = re.compile(rf"^GROUP RX {re.escape(source)} #\d+: {re.escape(text)}$")
    return any(pattern.match(line) for line in atom.lines[start:])


def received_usb_group(atom: Atom, source: str, text: str, start: int) -> bool:
    pattern = re.compile(rf"^USB_GROUP_RX SRC={re.escape(source)} ID=\d+ HEX={text.encode('utf-8').hex().upper()}$")
    return any(pattern.match(line) for line in atom.lines[start:])


def direct_trial(atoms: list[Atom], sender: Atom, receiver: Atom, text: str) -> bool:
    until(atoms, lambda: False, 2)
    sent_at, recv_at = len(sender.lines), len(receiver.lines)
    payload = text.encode("utf-8")
    sender.send("z " + payload.hex() + "\n")
    def complete():
        sent = any(line.startswith("RELIABLE SENT") for line in sender.lines[sent_at:])
        received = any(line.startswith("USB_RX ") and " PID=F0 HEX=" + payload.hex().upper() in line.upper()
                       for line in receiver.lines[recv_at:])
        return sent and received
    return until(atoms, complete, 60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", default="COM5")
    parser.add_argument("--b", default="COM6")
    parser.add_argument("--reverse-first", action="store_true")
    parser.add_argument("--direct-only", action="store_true")
    parser.add_argument("--host-hex", action="store_true")
    parser.add_argument("--ordering-loss", action="store_true")
    args = parser.parse_args()
    atoms: list[Atom] = []
    result = {"ports": [args.a, args.b], "checks": {}}
    try:
        a, b = Atom(args.a), Atom(args.b)
        atoms = [a, b]
        until(atoms, lambda: False, 3)
        a.send("group show\n")
        b.send("group show\n")
        if not until(atoms, lambda: all(any("GROUP MODE=" in line for line in x.lines) for x in atoms), 5):
            raise RuntimeError("group show did not respond on both ports")
        calls = []
        for atom in atoms:
            show = next(line for line in reversed(atom.lines) if "GROUP MODE=" in line)
            match = re.search(r"LOCAL=([A-Z0-9]+)", show)
            if not match:
                raise RuntimeError(f"cannot read callsign on {atom.port}")
            calls.append(match.group(1))
        if calls[0] == calls[1]:
            raise RuntimeError("both ATOMs use the same local callsign")
        if args.direct_only:
            for atom in atoms:
                atom.send("group off\n")
            until(atoms, lambda: False, 1)
            result["checks"]["direct_a_to_b"] = direct_trial(atoms, a, b, "直接通信 横浜市")
            result["checks"]["direct_b_to_a"] = direct_trial(atoms, b, a, "直接通信 繁體中文")
            if not all(result["checks"].values()):
                raise RuntimeError("direct reliable chat failed")
            print("PASS: bidirectional direct reliable UTF-8 chat", flush=True)
            return 0
        for atom in atoms:
            atom.send("group on\n")
        if not until(atoms, lambda: all(any("GROUP MODE=on" in line for line in x.lines) for x in atoms), 5):
            raise RuntimeError("group on did not succeed on both ports")

        directions = [
            (a, b, calls[0], "横浜市 グループ試験", "a_to_b"),
            (b, a, calls[1], "繁體中文 雙向測試", "b_to_a"),
        ]
        if args.reverse_first:
            directions.reverse()
        for sender, receiver, source, text, label in directions:
            # Allow codec/RX DMA to settle after the preceding transmission.
            until(atoms, lambda: False, 2)
            start = len(receiver.lines)
            sender.send((f"k {text.encode('utf-8').hex()}\n" if args.host_hex else f"g {text}\n"))
            ok = until(atoms, lambda: received(receiver, source, text, start) and
                       (not args.host_hex or received_usb_group(receiver, source, text, start)), 25)
            result["checks"][label] = ok
            if not ok:
                raise RuntimeError(f"{label}: no GROUP RX on {receiver.port}")

        if args.host_hex:
            print("PASS: bidirectional USB-host group UTF-8 chat", flush=True)
            return 0

        if args.ordering_loss:
            b.send("q")
            if not until(atoms, lambda: any("LIVE RX stopped" in line for line in b.lines[-5:]), 4):
                raise RuntimeError("could not stop B receiver for ordering test")
            start_a, start_b = len(a.lines), len(b.lines)
            first, second = "順序 01 横浜市", "順序 02 繁體中文"
            a.send(f"g {first}\n")
            if not until(atoms, lambda: any("GROUP TX OK" in line for line in a.lines[start_a:]), 15):
                raise RuntimeError("first group transmission failed")
            b.send("l")
            if not until(atoms, lambda: any("STATE RX LISTEN" in line for line in b.lines[start_b:]), 5):
                raise RuntimeError("B receiver did not resume")
            second_start = len(a.lines)
            a.send(f"g {second}\n")
            if not until(atoms, lambda: any("GROUP TX OK" in line for line in a.lines[second_start:]), 15):
                raise RuntimeError("second group transmission failed")
            if not until(atoms, lambda: received(b, calls[0], first, start_b) and
                         received(b, calls[0], second, start_b), 60):
                raise RuntimeError("missing group message was not repaired")
            tx_ids = list(dict.fromkeys(int(match.group(1)) for line in a.lines[start_a:]
                      if (match := re.match(r"GROUP WIRE TX type=1 id=(\d+)$", line))))
            rx_ids = [int(match.group(1)) for line in b.lines[start_b:]
                      if (match := re.match(r"GROUP WIRE RX type=1 id=(\d+) from=" + re.escape(calls[0]) + r"$", line))]
            if len(tx_ids) < 2 or tx_ids[1] not in rx_ids or tx_ids[0] not in rx_ids:
                raise RuntimeError("ordering test did not observe both wire IDs")
            if rx_ids.index(tx_ids[1]) >= rx_ids.index(tx_ids[0]):
                raise RuntimeError("wire order was not inverted; repeat the test")
            delivered = [line for line in b.lines[start_b:] if line.startswith(f"GROUP RX {calls[0]} #")]
            texts = [line.split(": ", 1)[1] for line in delivered]
            result["checks"]["ordered_recovery"] = texts == [first, second]
            if not result["checks"]["ordered_recovery"]:
                raise RuntimeError(f"out-of-order delivery: {texts!r}")
            print("PASS: AX.25 group recovery delivered both messages in order", flush=True)
            return 0

        # Deliberately stop B's microphone while A sends one DATA. Once B
        # resumes, A's periodic SUMMARY should trigger NACK and rebroadcast.
        b.send("q")
        if not until(atoms, lambda: any("LIVE RX stopped" in line for line in b.lines[-5:]), 4):
            raise RuntimeError("could not stop B receiver for loss test")
        start_a, start_b = len(a.lines), len(b.lines)
        lost_text = "SUMMARY NACK 復旧試験"
        a.send(f"g {lost_text}\n")
        if not until(atoms, lambda: any("GROUP TX OK" in line for line in a.lines[start_a:]), 15):
            raise RuntimeError("A did not finish loss-test transmission")
        b.send("l")
        ok = until(atoms, lambda: received(b, calls[0], lost_text, start_b), 35)
        result["checks"]["summary_nack_recovery"] = ok
        result["checks"]["nack_seen"] = any("GROUP WIRE TX type=2" in line for line in b.lines[start_b:])
        result["checks"]["summary_seen"] = any("GROUP WIRE RX type=3" in line for line in b.lines[start_b:])
        if not all(result["checks"].values()):
            raise RuntimeError("SUMMARY/NACK recovery did not complete")
        print("PASS: bidirectional UTF-8 group chat and SUMMARY/NACK recovery", flush=True)
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", flush=True)
        return 1
    finally:
        for atom in atoms:
            try:
                atom.send("group off\n")
            except serial.SerialException:
                pass
        result["logs"] = {atom.port: atom.lines for atom in atoms}
        result["pass"] = bool(result["checks"]) and all(result["checks"].values())
        run = ROOT / "runs" / ("group-chat-two-atom-" + time.strftime("%Y%m%d-%H%M%S"))
        run.mkdir(parents=True, exist_ok=True)
        (run / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved: {run}", flush=True)
        for atom in atoms:
            atom.close()


if __name__ == "__main__":
    raise SystemExit(main())
