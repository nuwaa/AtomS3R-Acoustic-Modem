"""Manual KISS sender: python send_test.py [--message "HELLO JN1EEP"]."""
import argparse
import socket
import time
import tx_message

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--message',help='One-time text override; otherwise use message.json.')
    args = parser.parse_args()
    try:
        text = tx_message.load() if args.message is None else tx_message.validate(args.message)
    except (ValueError,KeyError) as exc:
        parser.error(str(exc))
    packet,frame = tx_message.packet(text)
    print('TX JN1EEP > APRS:',text)
    print('Expected hex (no FCS):',frame.hex(' ').upper())
    print('In Serial Monitor send r. When REC appears, press Enter here.')
    input()
    with socket.create_connection(('127.0.0.1',8001),timeout=3) as sock:
        sock.sendall(packet)
        time.sleep(0.2)
    print('Queued one packet to Dire Wolf channel 0.')

if __name__ == '__main__':
    main()
