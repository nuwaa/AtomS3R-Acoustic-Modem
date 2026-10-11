"""Browser chat UI for an ATOM S3R connected through normal USB CDC."""
import argparse
import json
import re
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial
from serial.tools import list_ports

RX = re.compile(r"^USB_RX SRC=(\S+) DEST=(\S+) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]*)$")
GROUP_RX = re.compile(r"^USB_GROUP_RX SRC=([A-Z0-9]{1,6}) ID=(\d+) HEX=([0-9A-Fa-f]+)$")
RELIABLE_CHAT = re.compile(r"^RELIABLE (START|SENT|FAILED|BUSY_OR_INVALID)\b.*PID=F0\b")
HTML = r"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATOM USB Chat</title><style>
body{font-family:"Yu Gothic UI",sans-serif;background:#10151d;color:#eef3f8;margin:0}main{max-width:760px;margin:auto;height:100vh;display:flex;flex-direction:column}
header{padding:16px 18px;background:#172231;font-weight:700;display:flex;align-items:center;gap:12px;flex-wrap:wrap}#status{font-size:13px;color:#75d7a2;margin-left:10px}select{background:#0f1721;color:white;border:1px solid #42556b;border-radius:9px;padding:7px}
#log{flex:1;overflow:auto;padding:16px}.msg{background:#1b2735;border-radius:14px;padding:10px 13px;margin:8px 0;white-space:pre-wrap}.mine{background:#174a3a;margin-left:15%}.who{font-size:12px;color:#9fb1c4;margin-bottom:4px}
form{display:flex;gap:8px;padding:12px;background:#172231}input{flex:1;min-width:0;border:1px solid #42556b;border-radius:12px;background:#0f1721;color:white;padding:12px;font-size:16px}button{border:0;border-radius:12px;background:#27a96f;color:white;font-weight:700;padding:0 20px;font-size:16px}
</style><main><header>ATOM USB Chat <select id="mode" aria-label="AX.25チャットモード"><option value="direct">直接</option><option value="group">グループ CHAT</option></select><span id="status">接続中...</span></header><div style="padding:10px 18px;background:#1b2735;display:flex;align-items:center;gap:8px;flex-wrap:wrap"><span id="bell-state">Bell 103: 停止中</span><button type="button" data-bell="caller">発呼</button><button type="button" data-bell="answerer">応答</button><button type="button" data-bell="stop">切断</button></div><div id="log"></div><form id="form"><input id="text" maxlength="500" placeholder="日本語・繁體中文メッセージ" autofocus><button>送信</button></form></main>
<script>let since=0;const log=document.querySelector('#log'),status=document.querySelector('#status');
function add(e){const d=document.createElement('div');d.className='msg '+(e.who==='自分'?'mine':'');const w=document.createElement('div');w.className='who';w.textContent=e.who;const t=document.createElement('div');t.textContent=e.text;d.append(w,t);log.append(d);log.scrollTop=log.scrollHeight}
async function poll(){try{const r=await fetch('/events?since='+since);const j=await r.json();status.textContent=j.status;document.querySelector('#mode').value=j.mode;document.querySelector('#mode').disabled=j.bell!=='off';document.querySelector('#bell-state').textContent='Bell 103: '+j.bell;for(const e of j.events){add(e);since=e.id}}catch(e){status.textContent='再接続中...'}setTimeout(poll,400)}
document.querySelector('#mode').onchange=async e=>{const mode=e.target.value;const r=await fetch('/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});if(!r.ok)status.textContent=await r.text()};
document.querySelectorAll('[data-bell]').forEach(b=>b.onclick=async()=>{const r=await fetch('/bell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:b.dataset.bell})});if(!r.ok)status.textContent=await r.text()});
document.querySelector('#form').onsubmit=async e=>{e.preventDefault();const i=document.querySelector('#text'),text=i.value;if(!text)return;const r=await fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});if(r.ok)i.value='';else status.textContent=await r.text()};poll();</script></html>"""


class Bridge:
    def __init__(self, port_name):
        self.port_name = port_name
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.events = []
        self.recent_lines = deque(maxlen=100)
        self.next_id = 1
        self.status = f"{port_name} 接続中"
        self.port = serial.Serial(port_name, 115200, timeout=0.1, write_timeout=2)
        time.sleep(0.4)
        self.port.reset_input_buffer()
        self.status = f"{port_name} 接続済み"
        self.mode = "direct"
        self.bell = "off"
        self.bell_pending = False
        self.direct_queue = deque()
        self.direct_active = None
        threading.Thread(target=self.reader, daemon=True).start()
        self.set_mode("direct")

    def add(self, who, text):
        with self.lock:
            self.events.append({"id": self.next_id, "who": who, "text": text})
            self.next_id += 1
            self.events = self.events[-200:]

    def send(self, text):
        diagnostic = text.strip()
        if diagnostic in ("/rx-off", "/rx-on"):
            if self.bell != "off":
                raise ValueError("Bell 103接続中はAX.25受信診断を使用できません")
            self.write_command(b"q" if diagnostic == "/rx-off" else b"l")
            self.add("診断", "ATOMへ音響受信の" + ("停止" if diagnostic == "/rx-off" else "再開") + "を指示しました")
            return
        payload = text.encode("utf-8")
        with self.lock:
            if self.bell != "off":
                if self.bell != "接続済み":
                    raise ValueError("Bell 103接続待ちです")
                if self.bell_pending:
                    raise ValueError("前のBell 103本文のACK待ちです")
                if not 1 <= len(payload) <= 70 or "\n" in text or "\r" in text:
                    raise ValueError("Bell 103本文は改行なしのUTF-8で1～70バイトです")
                self.write_command(b"bell103 data send " + payload + b"\n")
                self.bell_pending = True
                who = "自分（Bell 103）"
            else:
                mode = self.mode
                limit = 198 if mode == "group" else 1500
                if not 1 <= len(payload) <= limit:
                    raise ValueError(f"本文はUTF-8で1～{limit}バイトです")
                if mode == "group":
                    self.write_command(f"k {payload.hex()}\n".encode("ascii"))
                    who = "自分（グループ）"
                else:
                    if len(self.direct_queue) >= 16:
                        raise ValueError("直接チャットの送信待ちは16件までです")
                    self.direct_queue.append((text, payload))
                    if self.direct_active is None:
                        self.start_next_direct()
                    who = "自分（送信待ち）"
        self.add(who, text)

    def start_next_direct(self):
        """Call with self.lock held; retain the head until SENT or FAILED."""
        if self.direct_active is not None or not self.direct_queue:
            return
        self.direct_active = self.direct_queue[0]
        self.write_command(f"z {self.direct_active[1].hex()}\n".encode("ascii"))

    def bell_action(self, action):
        if action not in ("caller", "answerer", "stop"):
            raise ValueError("Bell 103 action must be caller, answerer, or stop")
        with self.lock:
            if action != "stop" and self.bell != "off":
                raise ValueError("Bell 103は既に開始しています。先に切断してください")
            if action != "stop" and self.direct_queue:
                raise ValueError("直接チャットの送達待ちが終わってからBell 103へ切り替えてください")
            if action != "stop":
                self.write_command(b"group off\n")
                self.mode = "direct"
            self.write_command(f"bell103 auto {action}\n".encode("ascii"))
            self.bell = "off" if action == "stop" else "接続中（" + ("発呼" if action == "caller" else "応答") + "）"
            self.bell_pending = False
            self.status = f"{self.port.port} 接続済み · {'直接' if action == 'stop' else 'Bell 103'}"
        self.add("システム", "Bell 103 " + ("切断" if action == "stop" else "発呼" if action == "caller" else "応答待ち"))

    def set_mode(self, mode):
        if mode not in ("direct", "group"):
            raise ValueError("mode must be direct or group")
        with self.lock:
            if self.bell != "off":
                raise ValueError("Bell 103を切断してからAX.25を選んでください")
            if mode != "direct" and self.direct_queue:
                raise ValueError("直接チャットの送達待ちが終わってから切り替えてください")
            self.write_command(f"group {'on' if mode == 'group' else 'off'}\n".encode("ascii"))
            self.mode = mode
            self.status = f"{self.port.port} 接続済み · {'グループ CHAT' if mode == 'group' else '直接'}"

    def write_command(self, command):
        with self.write_lock:
            for offset in range(0, len(command), 32):
                self.port.write(command[offset:offset + 32])
                self.port.flush()
                time.sleep(0.01)

    def reader(self):
        while True:
            try:
                line = self.port.readline().decode("utf-8", errors="replace").strip()
            except Exception as error:
                self.status = f"USB切断: {error}"
                with self.lock:
                    self.bell = "off"
                    self.bell_pending = False
                    abandoned = list(self.direct_queue)
                    self.direct_active = None
                    self.direct_queue.clear()
                for text, _ in abandoned:
                    self.add("未送信（USB切断）", text)
                try:
                    self.port.close()
                except Exception:
                    pass
                while True:
                    time.sleep(1)
                    replacement = None
                    try:
                        with self.lock:
                            replacement = serial.Serial(self.port_name, 115200, timeout=0.1, write_timeout=2)
                            time.sleep(0.4)
                            replacement.reset_input_buffer()
                            self.port = replacement
                            self.write_command(f"group {'on' if self.mode == 'group' else 'off'}\n".encode("ascii"))
                            self.status = f"{self.port_name} 再接続済み · {'グループ CHAT' if self.mode == 'group' else '直接'}"
                        self.add("システム", "ATOM USB再接続")
                        break
                    except Exception:
                        if replacement is not None:
                            try:
                                replacement.close()
                            except Exception:
                                pass
                        self.status = f"{self.port_name} 再接続待ち"
                continue
            self.handle_line(line)

    def handle_line(self, line):
        if line:
            with self.lock:
                self.recent_lines.append(line[:300])
        if line.startswith(("LIVE RX stopped", "STATE RX LISTEN")):
            self.add("ATOM", line)
            return
        direct_status = RELIABLE_CHAT.match(line)
        if direct_status:
            outcome = direct_status.group(1)
            if outcome != "START":
                with self.lock:
                    current = self.direct_active
                    cancelled = []
                    if current is not None:
                        self.direct_queue.popleft()
                        self.direct_active = None
                        if outcome != "SENT":
                            cancelled = list(self.direct_queue)
                            self.direct_queue.clear()
                        elif self.mode == "direct" and self.bell == "off":
                            self.start_next_direct()
                if current is not None:
                    self.add("送達" if outcome == "SENT" else "送信失敗", current[0])
                    for text, _ in cancelled:
                        self.add("未送信", text)
            return
        if line.startswith("BELL103 AUTO RX TEXT "):
            self.add("Bell 103", line.partition(": ")[2])
            return
        if line.startswith("BELL103 AUTO RX CONTROL "):
            if "state=connected" in line:
                with self.lock:
                    self.bell = "接続済み"
                self.add("システム", "Bell 103 接続済み")
            return
        if line.startswith(("BELL103 SESSION STOP", "BELL103 AUTO CONNECT TIMEOUT")):
            with self.lock:
                self.bell = "off"
                self.bell_pending = False
            self.add("システム", line)
            return
        if line.startswith(("BELL103 AUTO ACK OK", "BELL103 AUTO DATA RETRIES EXHAUSTED", "BELL103 DATA QUEUE FAILED", "ERROR: Bell 103")):
            with self.lock:
                self.bell_pending = False
            self.add("Bell 103", line)
            return
        if line.startswith("GROUP WIRE "):
            return
        if line.startswith("GROUP TX FAILED"):
            self.status = line
            self.add("システム", line)
            return
        group = GROUP_RX.match(line)
        if group:
            try:
                text = bytes.fromhex(group.group(3)).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                text = "[UTF-8デコード失敗]"
            self.add(f"{group.group(1)}>CHAT（グループ）", text)
            return
        match = RX.match(line)
        if not match or match.group(3).upper() != "F0":
            return
        try:
            text = bytes.fromhex(match.group(4)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            text = "[UTF-8デコード失敗]"
        self.add(f"{match.group(1)}>{match.group(2)}", text)


def detect_port():
    ports = list(list_ports.comports())
    devices = [item.device for item in ports if item.vid == 0x303A]
    return devices[0] if devices else CFG.get("port", "COM5")


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, status, content_type, data):
            try:
                self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass  # The browser closed a poll while its response was being sent.
        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                return self.send_bytes(200, "text/html; charset=utf-8", HTML.encode())
            if self.path == "/debug":
                with bridge.lock:
                    lines = list(bridge.recent_lines)
                return self.send_bytes(200, "text/plain; charset=utf-8", ("\n".join(lines) + "\n").encode("utf-8"))
            if self.path.startswith("/events"):
                try: since = int(self.path.partition("since=")[2] or 0)
                except ValueError: since = 0
                with bridge.lock:
                    events = [item for item in bridge.events if item["id"] > since]
                    mode = bridge.mode
                    bell = bridge.bell
                data = json.dumps({"status": bridge.status, "mode": mode, "bell": bell, "events": events}, ensure_ascii=False).encode()
                return self.send_bytes(200, "application/json; charset=utf-8", data)
            self.send_error(404)
        def do_POST(self):
            if self.path not in ("/send", "/mode", "/bell"): return self.send_error(404)
            try:
                length = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(length))
                if self.path == "/mode": bridge.set_mode(body["mode"])
                elif self.path == "/bell": bridge.bell_action(body["action"])
                else: bridge.send(str(body["text"]))
                data = b"OK"
                return self.send_bytes(200, "text/plain", data)
            except Exception as error:
                return self.send_bytes(400, "text/plain; charset=utf-8", str(error).encode())
        def log_message(self, *_): pass
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", default=detect_port()); parser.add_argument("--listen", default="127.0.0.1"); parser.add_argument("--http-port", type=int, default=8766); args = parser.parse_args()
    bridge = Bridge(args.port)
    print(f"ATOM USB Chat: http://{args.listen}:{args.http_port}/ ({args.port})", flush=True)
    ThreadingHTTPServer((args.listen, args.http_port), handler_for(bridge)).serve_forever()
