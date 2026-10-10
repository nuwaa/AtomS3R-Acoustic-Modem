"""Verify the installed Wintun route with Windows' standard ping.exe."""
import argparse,json,re,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--target",default="10.23.0.2");parser.add_argument("--count",type=int,default=2);args=parser.parse_args()
    command=["ping.exe","-n",str(args.count),"-w","30000",args.target]
    run=subprocess.run(command,capture_output=True,text=True,encoding="oem",errors="replace")
    output=run.stdout+run.stderr;replies=re.findall(r"Reply from .*?time[=<](\d+)ms",output,re.I)
    passed=run.returncode==0 and len(replies)==args.count
    folder=ROOT/"runs"/(time.strftime("%Y%m%d-%H%M%S")+"-windows-ping");folder.mkdir(parents=True)
    result={"pass":passed,"target":args.target,"sent":args.count,"received":len(replies),"rtt_ms":[int(x) for x in replies],"command":command}
    (folder/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");(folder/"ping.txt").write_text(output,encoding="utf-8")
    print(output);print("Saved:",folder);print("PASS" if passed else "FAIL",result);raise SystemExit(0 if passed else 1)

if __name__=="__main__":main()
