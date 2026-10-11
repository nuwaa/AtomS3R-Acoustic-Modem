"""Drop one ACK on purpose; verify retry and single delivery over the air."""

import argparse
import time

from test_bell103_session_air import serial, send, step, until


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

            send(caller, "bell103 data send RETRY01")
            until(caller, args.caller, "BELL103 DATA QUEUED", 5)
            send(answerer, "bell103 data rx")
            until(answerer, args.answerer, "BELL103 REC 6 seconds", 6)
            send(caller, "bell103 data tx")
            until(caller, args.caller, "BELL103 DATA TX type=1", 12)
            until(answerer, args.answerer, "BELL103 DATA RX NEW len=7 text=RETRY01", 25)

            # Send ACK while caller is not receiving it.
            send(answerer, "bell103 data tx")
            until(answerer, args.answerer, "BELL103 DATA TX type=2", 12)
            time.sleep(9)

            send(answerer, "bell103 data rx")
            until(answerer, args.answerer, "BELL103 REC 6 seconds", 6)
            send(caller, "bell103 data tx")
            until(caller, args.caller, "BELL103 DATA TX type=1", 12)
            until(answerer, args.answerer, "BELL103 DATA RX DUPLICATE OR IGNORED", 25)

            send(caller, "bell103 data rx")
            until(caller, args.caller, "BELL103 REC 6 seconds", 6)
            send(answerer, "bell103 data tx")
            until(answerer, args.answerer, "BELL103 DATA TX type=2", 12)
            until(caller, args.caller, "BELL103 DATA ACK OK", 25)
            print("TEST PASS: lost ACK recovered; DATA delivered once", flush=True)
        finally:
            for name, port in ((args.caller, caller), (args.answerer, answerer)):
                try:
                    send(port, "bell103 session stop")
                    until(port, name, "ACOUSTIC MODE=ax25", 5)
                except (OSError, RuntimeError) as exc:
                    print(f"WARNING: {name} cleanup: {exc}", flush=True)


if __name__ == "__main__":
    main()
