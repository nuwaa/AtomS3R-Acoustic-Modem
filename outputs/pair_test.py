"""Two-device acoustic AX.25 test: python pair_test.py --a COM5 --b COM6."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/'environment/settings.json').read_text(encoding='utf-8'))
sys.path.insert(0,cfg['python_libraries'])
import serial

def trial(sender,receiver,text,label):
    sender.reset_input_buffer(); receiver.reset_input_buffer()
    sender.write(('t '+text+'\n').encode('ascii'))
    sent=received=False; lines=[]; deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        for device,side in ((sender,'TX'),(receiver,'RX')):
            line=device.readline().decode('utf-8',errors='replace').strip()
            if line:
                print(label,side,line,flush=True); lines.append((side,line))
                sent |= side=='TX' and line.startswith('TX OK')
                received |= side=='RX' and line.startswith('TEXT:') and text in line
        if sent and received:return True,lines
    return False,lines

def main():
    p=argparse.ArgumentParser(); p.add_argument('--a',default='COM5');p.add_argument('--b',default='COM6');args=p.parse_args()
    folder=ROOT/'runs'/(time.strftime('%Y%m%d-%H%M%S')+'-atom-pair');folder.mkdir(parents=True)
    a=serial.Serial(args.a,115200,timeout=.05);b=serial.Serial(args.b,115200,timeout=.05);time.sleep(.5)
    try:
        ab,ablog=trial(a,b,'HELLO FROM ATOMA','A_TO_B');time.sleep(.8)
        ba,balog=trial(b,a,'HELLO FROM ATOMB','B_TO_A')
    finally:a.close();b.close()
    result={'A_to_B':ab,'B_to_A':ba,'port_A':args.a,'port_B':args.b}
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (folder/'logs.json').write_text(json.dumps({'A_to_B':ablog,'B_to_A':balog},indent=2),encoding='utf-8')
    print('Saved:',folder);print('PASS' if ab and ba else 'FAIL',result)
    raise SystemExit(0 if ab and ba else 1)
if __name__=='__main__':main()
