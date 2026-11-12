"""Small move/return test of our player-thread mailbox hook, isolated Cemu only."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'HyruleBlocks'))
from bridge import Process

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--pid',type=int,required=True)
    p.add_argument('--cemu-log',type=Path,required=True)
    args=p.parse_args()
    game=Process(args.pid,args.cemu_log)
    original=game.position()
    report={'pid':args.pid,'original':original,'distance_requested':0.25}
    def move(point):
        if not game.nudge(point):
            raise RuntimeError('Another mod command is pending')
        deadline=time.monotonic()+2
        while game.get(0x10)==3 and time.monotonic()<deadline:
            time.sleep(0.02)
        if game.get(0x10)==3:
            game.set(0x10,0)
            raise RuntimeError('Player hook did not consume movement; request cancelled')
        if game.get(0x14,'i')!=2:
            raise RuntimeError('Player hook rejected the verified setMtx call')
        time.sleep(0.25)
        return game.position()
    try:
        target=(original[0]+0.25,original[1],original[2])
        result=move(target)
        report['after_move']=result
        report['move_error']=sum((a-b)**2 for a,b in zip(result,target))**0.5
        restored=move(original)
        report['after_return']=restored
        report['return_error']=sum((a-b)**2 for a,b in zip(restored,original))**0.5
        report['passed']=report['move_error']<0.1 and report['return_error']<0.1
    except Exception as e:
        report['passed']=False
        report['error']=str(e)
    finally:
        game.k.CloseHandle(game.handle)
        (ROOT/'movement-test.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    if not report['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
