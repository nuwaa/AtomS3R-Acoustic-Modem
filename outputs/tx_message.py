"""Shared persistent ASCII message and AX.25/KISS encoder."""
import json
from pathlib import Path
MESSAGE_FILE = Path(__file__).with_name('message.json')
DEFAULT_TEXT = 'CQ CQ CQ DE JN1EEP K'

def validate(text):
    if not isinstance(text,str) or not 1 <= len(text) <= 120 or any(not 0x20 <= ord(c) <= 0x7e for c in text):
        raise ValueError('Use 1-120 printable ASCII characters (letters, numbers, spaces, punctuation).')
    if not text.strip():
        raise ValueError('Message must contain a non-space character.')
    return text

def load():
    if not MESSAGE_FILE.exists():
        return DEFAULT_TEXT
    return validate(json.loads(MESSAGE_FILE.read_text(encoding='utf-8'))['text'])

def save(text):
    text = validate(text)
    temporary = MESSAGE_FILE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'text':text},indent=2)+'\n',encoding='utf-8')
    temporary.replace(MESSAGE_FILE)

def packet(text=None):
    text = load() if text is None else validate(text)
    def address(call,last):
        return bytes(ord(c)<<1 for c in call.ljust(6))+bytes([0x60|int(last)])
    frame = address('APRS',False)+address('JN1EEP',True)+b'\x03\xf0'+text.encode('ascii')
    payload = (b'\0'+frame).replace(b'\xdb',b'\xdb\xdd').replace(b'\xc0',b'\xdb\xdc')
    return b'\xc0'+payload+b'\xc0',frame
