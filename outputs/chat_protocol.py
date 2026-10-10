"""Transport-independent UTF-8 chat datagram format."""
from __future__ import annotations
import json,time,uuid

VERSION=1
MAX_DATAGRAM=1200
MAX_NAME_BYTES=48
MAX_TEXT_BYTES=1000

def _utf8(value,limit,label):
    if not isinstance(value,str):raise ValueError(label+" must be text")
    encoded=value.encode("utf-8")
    if not encoded or len(encoded)>limit:raise ValueError(f"{label} must be 1..{limit} UTF-8 bytes")
    return value

def chat(sender,text,message_id=None,sent_at=None):
    return {"v":VERSION,"type":"chat","id":message_id or uuid.uuid4().hex,"sender":_utf8(sender,MAX_NAME_BYTES,"sender"),
            "text":_utf8(text,MAX_TEXT_BYTES,"text"),"sent_at":int(time.time()*1000) if sent_at is None else int(sent_at)}

def ack(message_id):return {"v":VERSION,"type":"ack","ack_id":str(message_id)}

def encode(message):
    data=json.dumps(message,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode("utf-8")
    if len(data)>MAX_DATAGRAM:raise ValueError(f"chat datagram exceeds {MAX_DATAGRAM} bytes")
    return data

def decode(data):
    if not isinstance(data,(bytes,bytearray)) or len(data)>MAX_DATAGRAM:raise ValueError("invalid datagram size")
    message=json.loads(bytes(data).decode("utf-8"))
    if not isinstance(message,dict) or message.get("v")!=VERSION:raise ValueError("unsupported chat version")
    kind=message.get("type")
    if kind=="chat":
        identifier=message.get("id")
        if not isinstance(identifier,str) or not 8<=len(identifier)<=64:raise ValueError("invalid message id")
        _utf8(message.get("sender"),MAX_NAME_BYTES,"sender");_utf8(message.get("text"),MAX_TEXT_BYTES,"text")
        if not isinstance(message.get("sent_at"),int):raise ValueError("invalid timestamp")
    elif kind=="ack":
        if not isinstance(message.get("ack_id"),str):raise ValueError("invalid ack")
    else:raise ValueError("unknown message type")
    return message
