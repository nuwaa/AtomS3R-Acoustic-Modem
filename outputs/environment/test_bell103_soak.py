"""Timed two-ATOM Bell 103 air test; logs every DATA, ACK, retry and delivery."""

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from test_bell103_session_air import serial, send, until

TX_DATA = re.compile(r"BELL103 AUTO TX DATA type=1 seq=(\d+)")
RX_TEXT = re.compile(r"BELL103 AUTO RX TEXT len=\d+: (SOAK\d{3})$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", default="COM5")
    parser.add_argument("--answerer", default="COM6")
    parser.add_argument("--minutes", type=float, default=30)
    parser.add_argument("--interval", type=float, default=45)
    args = parser.parse_args()
    if args.caller.upper() == args.answerer.upper() or not 1 <= args.minutes <= 120 or not 5 <= args.interval <= 300:
        raise SystemExit("Use distinct COM ports, minutes 1..120, interval 5..300 seconds")

    runs = Path(__file__).resolve().parents[1] / "runs"
    runs.mkdir(exist_ok=True)
    stem = "bell103-soak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = runs / (stem + ".log")
    summary_path = runs / (stem + ".json")
    started = time.monotonic()
    deliveries = Counter()
    acknowledgements = Counter()
    tx_attempts = Counter()
    connected = set()
    overture = answer_ready = hello = False
    sent = []
    failure = None
    restored = set()

    with log_path.open("w", encoding="utf-8") as log:
        def emit(message):
            line = datetime.now().isoformat(timespec="seconds") + " " + message
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        emit(f"START caller={args.caller} answerer={args.answerer} minutes={args.minutes} interval={args.interval}")
        try:
            with serial.Serial(args.caller, 115200, timeout=.1, write_timeout=2) as caller, \
                 serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
                ports = ((args.caller, caller), (args.answerer, answerer))

                def poll(deadline, done):
                    nonlocal overture, answer_ready, hello
                    next_progress = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        for name, port in ports:
                            line = port.readline().decode("utf-8", "replace").strip()
                            if not line:
                                continue
                            emit(f"{name}: {line}")
                            if any(marker in line for marker in (
                                "BELL103 AUTO CONNECT TIMEOUT",
                                "BELL103 AUTO DATA RETRIES EXHAUSTED",
                                "BELL103 AUTO TX CONTROL FAILED",
                                "BELL103 AUTO TX DATA FAILED",
                            )):
                                raise RuntimeError(f"{name}: {line}")
                            if name == args.answerer and "BELL103 AUTO RX READY" in line:
                                answer_ready = True
                            if name == args.caller and "BELL103 OVERTURE OK" in line:
                                overture = True
                            if name == args.caller and "BELL103 AUTO TX CONTROL type=1" in line:
                                if not overture:
                                    raise RuntimeError("HELLO preceded overture")
                                hello = True
                            if "BELL103 AUTO RX CONTROL" in line and "state=connected" in line:
                                connected.add(name)
                            tx = TX_DATA.search(line)
                            if tx:
                                tx_attempts[(name, int(tx.group(1)))] += 1
                            rx = RX_TEXT.search(line)
                            if rx:
                                deliveries[(name, rx.group(1))] += 1
                                if deliveries[(name, rx.group(1))] > 1:
                                    raise RuntimeError(f"duplicate delivery: {name} {rx.group(1)}")
                            if "BELL103 AUTO ACK OK" in line:
                                acknowledgements[name] += 1
                        if done():
                            return
                        if time.monotonic() >= next_progress:
                            emit(f"PROGRESS elapsed_s={int(time.monotonic()-started)} sent={len(sent)} ack={sum(acknowledgements.values())} retransmissions={max(0,sum(tx_attempts.values())-len(sent))}")
                            next_progress += 60
                    if not done():
                        raise TimeoutError("timed out waiting for Bell 103 progress")

                try:
                    time.sleep(2)
                    caller.reset_input_buffer()
                    answerer.reset_input_buffer()
                    send(answerer, "bell103 auto answerer")
                    send(caller, "bell103 auto caller")
                    poll(time.monotonic() + 130, lambda: len(connected) == 2 and overture and answer_ready and hello)
                    linked_at = time.monotonic()
                    emit("CONNECTED; 30-minute timer starts now" if args.minutes == 30 else "CONNECTED; timer starts now")
                    index = 0
                    while time.monotonic() - linked_at < args.minutes * 60 or index < 2:
                        index += 1
                        message = f"SOAK{index:03d}"
                        sender_name, sender = ports[(index - 1) % 2]
                        receiver_name, _ = ports[index % 2]
                        ack_before = acknowledgements[sender_name]
                        sent.append((sender_name, receiver_name, message))
                        send(sender, f"bell103 data send {message}")
                        emit(f"SEND {message} {sender_name}->{receiver_name}")
                        poll(time.monotonic() + 180,
                             lambda: deliveries[(receiver_name, message)] == 1 and acknowledgements[sender_name] > ack_before)
                        emit(f"ACKED {message}")
                        until_next = min(linked_at + args.minutes * 60,
                                         time.monotonic() + args.interval)
                        poll(until_next, lambda: time.monotonic() >= until_next)
                    settle_until = time.monotonic() + 20
                    poll(settle_until, lambda: time.monotonic() >= settle_until)
                finally:
                    for name, port in ports:
                        try:
                            send(port, "bell103 auto stop")
                            until(port, name, "ACOUSTIC MODE=ax25", 18)
                            restored.add(name)
                        except (OSError, RuntimeError) as error:
                            emit(f"WARNING {name} cleanup: {error}")

            for sender_name, receiver_name, message in sent:
                if deliveries[(receiver_name, message)] != 1:
                    raise RuntimeError(f"{message}: delivery count {deliveries[(receiver_name, message)]}")
            if len(sent) < 2 or time.monotonic() - linked_at < args.minutes * 60:
                raise RuntimeError("soak duration was incomplete")
            if restored != {args.caller, args.answerer}:
                raise RuntimeError(f"AX.25 restore not confirmed: {restored}")
            emit(f"TEST PASS messages={len(sent)} ack={sum(acknowledgements.values())} tx_data={sum(tx_attempts.values())} retries={sum(tx_attempts.values())-len(sent)}")
        except (OSError, RuntimeError, TimeoutError, KeyboardInterrupt) as error:
            failure = str(error)
            emit(f"TEST FAILED: {failure}")
        finally:
            summary = {
                "status": "PASS" if failure is None else "FAILED",
                "failure": failure,
                "caller": args.caller,
                "answerer": args.answerer,
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "messages_sent": len(sent),
                "deliveries": {f"{name}/{message}": count for (name, message), count in deliveries.items()},
                "ack_count": dict(acknowledgements),
                "data_transmissions": sum(tx_attempts.values()),
                "retransmissions": max(0, sum(tx_attempts.values()) - len(sent)),
                "log": str(log_path),
            }
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            emit(f"Saved: {summary_path}")
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
