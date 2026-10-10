"""Configure two freshly flashed ATOM S3R units for bidirectional USB chat."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "environment/settings.json").read_text(encoding="utf-8"))
sys.path.insert(0, CFG["python_libraries"])
import serial


def command(port_name, text):
    with serial.Serial(port_name, 115200, timeout=0.2, write_timeout=2) as port:
        time.sleep(1.0)
        port.reset_input_buffer()
        port.write((text + "\n").encode("ascii"))
        port.flush()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            line = port.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(f"{port_name}: {line}")
            if line.startswith(("CONFIG ", "BOOT MODE=")):
                return
        raise RuntimeError(f"{port_name}: no response to {text!r}")


command("COM5", "c ATOMA ATOMB")
command("COM5", "boot normal")
command("COM6", "c ATOMB ATOMA")
command("COM6", "boot normal")
print("CHAT CONFIG OK: COM5=ATOMA, COM6=ATOMB, both BOOT NORMAL")
