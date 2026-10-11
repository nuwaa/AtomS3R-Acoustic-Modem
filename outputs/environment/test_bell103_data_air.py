"""Connect two ATOMs, then verify DATA and ACK over both Bell 103 bands."""

import argparse
import time

from test_bell103_session_air import serial
from test_bell103_session_air import send, step, until


def data_direction(sender, receiver, sender_name, receiver_name, message):
    sender.reset_input_buffer()
    receiver.reset_input_buffer()
    send(sender, f"bell103 data send {message}")
    until(sender, sender_name, "BELL103 DATA QUEUED", 5)
    send(receiver, "bell103 data rx")
    until(receiver, receiver_name, "BELL103 REC 6 seconds", 6)
    send(sender, "bell103 data tx")
    until(sender, sender_name, "BELL103 DATA TX type=1", 12)
    until(receiver, receiver_name, f"text={message}", 25)
    send(sender, "bell103 data rx")
    until(sender, sender_name, "BELL103 REC 6 seconds", 6)
    send(receiver, "bell103 data tx")
    until(receiver, receiver_name, "BELL103 DATA TX type=2", 12)
    until(sender, sender_name, "BELL103 DATA ACK OK", 25)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", required=True)
    parser.add_argument("--answerer", required=True)
    args = parser.parse_args()
    if args.caller.upper() == args.answerer.upper():
        raise SystemExit("Use two different COM ports")
    with serial.Serial(args.caller, 115200, timeout=.1, write_timeout=2) as caller, \
         serial.Serial(args.answerer, 115200, timeout=.1, write_timeout=2) as answerer:
        try:
            time.sleep(2)
            caller.reset_input_buffer()
            answerer.reset_input_buffer()
            send(caller, "bell103 session caller")
            send(answerer, "bell103 session answerer")
            until(caller, args.caller, "BELL103 SESSION START role=caller", 5)
            until(answerer, args.answerer, "BELL103 SESSION START role=answerer", 5)
            step(caller, answerer, args.caller, args.answerer, 1, "wait-confirm")
            step(answerer, caller, args.answerer, args.caller, 2, "wait-established")
            step(caller, answerer, args.caller, args.answerer, 3, "connected")
            step(answerer, caller, args.answerer, args.caller, 4, "connected")
            data_direction(caller, answerer, args.caller, args.answerer, "DATA01")
            data_direction(answerer, caller, args.answerer, args.caller, "DATA02")
            print("TEST PASS: two-way Bell 103 DATA/ACK over air", flush=True)
        finally:
            for name, port in ((args.caller, caller), (args.answerer, answerer)):
                try:
                    send(port, "bell103 session stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 5)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
