"""Small UTF-8 chat window for an ATOM S3R in normal USB mode."""
import json
import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial
from serial.tools import list_ports

RX = re.compile(r"^USB_RX SRC=(\S+) DEST=(\S+) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]*)$")


class ChatWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("ATOM USB Chat")
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.device = None

        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        self.port = tk.StringVar(value=self.detect_port())
        ttk.Label(bar, text="ATOM:").pack(side="left")
        self.port_box = ttk.Combobox(bar, textvariable=self.port, values=self.port_names(), width=12)
        self.port_box.pack(side="left", padx=6)
        ttk.Button(bar, text="接続", command=self.connect).pack(side="left")
        self.status = tk.StringVar(value="未接続")
        ttk.Label(bar, textvariable=self.status).pack(side="left", padx=10)

        self.log = tk.Text(root, state="disabled", wrap="word", font=("Yu Gothic UI", 12))
        self.log.pack(fill="both", expand=True, padx=8)

        send_bar = ttk.Frame(root, padding=8)
        send_bar.pack(fill="x")
        self.message = ttk.Entry(send_bar, font=("Yu Gothic UI", 12))
        self.message.pack(side="left", fill="x", expand=True)
        self.message.bind("<Return>", self.send)
        ttk.Button(send_bar, text="送信", command=self.send).pack(side="left", padx=(8, 0))

        root.geometry("680x460")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self.drain_events)
        root.after(100, self.connect)

    @staticmethod
    def port_names():
        return [item.device for item in list_ports.comports()]

    def detect_port(self):
        ports = list(list_ports.comports())
        espressif = [item.device for item in ports if item.vid == 0x303A]
        return espressif[0] if len(espressif) == 1 else CFG.get("port", "COM5")

    def connect(self):
        if self.device and self.device.is_open:
            self.device.close()
        try:
            self.device = serial.Serial(self.port.get(), 115200, timeout=0.1, write_timeout=2)
            time.sleep(0.4)
            self.device.reset_input_buffer()
            self.stop.clear()
            threading.Thread(target=self.reader, daemon=True).start()
            self.status.set(f"{self.port.get()} 接続済み")
            self.message.focus_set()
        except Exception as error:
            self.status.set(f"接続失敗: {error}")

    def write_command(self, command):
        for offset in range(0, len(command), 32):
            self.device.write(command[offset:offset + 32])
            self.device.flush()
            time.sleep(0.01)

    def send(self, _event=None):
        text = self.message.get()
        if not text:
            return "break"
        if not self.device or not self.device.is_open:
            self.status.set("ATOMへ接続してください")
            return "break"
        payload = text.encode("utf-8")
        if len(payload) > 1500:
            self.status.set("本文はUTF-8で1500バイトまでです")
            return "break"
        try:
            self.write_command(f"z {payload.hex()}\n".encode("ascii"))
            self.events.put(("自分", text))
            self.message.delete(0, "end")
        except Exception as error:
            self.status.set(f"送信失敗: {error}")
        return "break"

    def reader(self):
        while not self.stop.is_set() and self.device and self.device.is_open:
            try:
                line = self.device.readline().decode("utf-8", errors="replace").strip()
            except Exception as error:
                self.events.put(("status", f"USB切断: {error}"))
                return
            match = RX.match(line)
            if not match:
                continue
            source, destination, pid, encoded = match.groups()
            if pid.upper() != "F0":
                continue
            try:
                text = bytes.fromhex(encoded).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                text = "[UTF-8デコード失敗]"
            self.events.put((f"{source}>{destination}", text))

    def drain_events(self):
        while True:
            try:
                who, text = self.events.get_nowait()
            except queue.Empty:
                break
            if who == "status":
                self.status.set(text)
                continue
            self.log.configure(state="normal")
            self.log.insert("end", f"{who}: {text}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(50, self.drain_events)

    def close(self):
        self.stop.set()
        if self.device and self.device.is_open:
            self.device.close()
        self.root.destroy()


if __name__ == "__main__":
    app = tk.Tk()
    ChatWindow(app)
    app.mainloop()
