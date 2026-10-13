"""Summarize connection and message latency from a Bell 103 soak log."""

import argparse
import re
from datetime import datetime
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    events = []
    for line in args.log.read_text(encoding="utf-8").splitlines():
        try:
            stamp, message = line.split(" ", 1)
            events.append((datetime.fromisoformat(stamp), message))
        except (ValueError, IndexError):
            pass

    def first(marker):
        return next((time for time, message in events if marker in message), None)

    start = first("BELL103 AUTO OVERTURE START")
    overture = first("BELL103 OVERTURE OK")
    connected = first("CONNECTED; timer starts now") or first("CONNECTED; 30-minute timer starts now")
    if start and overture and connected:
        print(f"overture_s={(overture-start).total_seconds():.0f}")
        print(f"handshake_after_overture_s={(connected-overture).total_seconds():.0f}")
        print(f"connect_total_s={(connected-start).total_seconds():.0f}")

    sent = {}
    first_transmissions = []
    deliveries = []
    acks = []
    current = None
    for time, message in events:
        match = re.search(r"\bSEND (SOAK\d{3}) (COM\d+)->(COM\d+)\b", message)
        if match:
            sent[match.group(1)] = time
            current = (match.group(1), match.group(2), False)
        if current and not current[2] and message.startswith(current[1] + ": BELL103 AUTO TX DATA type=1"):
            first_transmissions.append((time-sent[current[0]]).total_seconds())
            current = (current[0], current[1], True)
        match = re.search(r"BELL103 AUTO RX TEXT len=\d+: (SOAK\d{3})$", message)
        if match and match.group(1) in sent:
            deliveries.append((time-sent[match.group(1)]).total_seconds())
        match = re.search(r"\bACKED (SOAK\d{3})\b", message)
        if match and match.group(1) in sent:
            acks.append((time-sent[match.group(1)]).total_seconds())
    for label, values in (("first_transmission", first_transmissions), ("delivery", deliveries), ("ack", acks)):
        if values:
            print(f"{label}_s count={len(values)} median={median(values):.1f} min={min(values):.1f} max={max(values):.1f}")


if __name__ == "__main__":
    main()
