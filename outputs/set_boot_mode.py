"""Read or save the firmware boot transport while the device is in normal command mode."""
import argparse,json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"environment/settings.json").read_text(encoding="utf-8"));sys.path.insert(0,CFG["python_libraries"])
import serial

def main():
    parser=argparse.ArgumentParser(description="Set persistent ATOM host transport boot mode")
    parser.add_argument("mode",choices=("show","normal","slip","ppp","reset"));parser.add_argument("--port",default="COM5")
    args=parser.parse_args();device=serial.Serial(args.port,115200,timeout=.2,write_timeout=2);time.sleep(.6);device.reset_input_buffer()
    device.write(("boot "+args.mode+"\n").encode("ascii"));device.flush();deadline=time.monotonic()+3;lines=[]
    while time.monotonic()<deadline:
        line=device.readline().decode("utf-8","replace").strip()
        if line:print(line);lines.append(line)
        if any(token in line for token in ("BOOT MODE=","ERROR:")):break
    device.close()
    if not any("BOOT MODE=" in line for line in lines):raise SystemExit("No boot-mode response. Put the device in normal mode, then retry.")

if __name__=="__main__":main()
