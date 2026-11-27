"""Run both RM-204 modules independently; return nonzero if either fails."""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('orders-root','history','allocation-root','archive-root'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    logs=ROOT/'private'/'logs'
    logs.mkdir(parents=True,exist_ok=True)
    log=logs/f"daily_compliance_{datetime.now():%Y%m%d_%H%M%S_%f}.log"
    jobs=[
        ('Trade Reconciliation',['backend/run_preview.py','--orders-root',str(a.orders_root),'--history',str(a.history),'--archive-root',str(a.archive_root),'--archive']),
        ('Investment Restrictions',['backend/investment_restrictions.py','--allocation-root',str(a.allocation_root),'--archive-root',str(a.archive_root),'--archive'])
    ]
    failed=False
    with log.open('w',encoding='utf-8') as f:
        for name,args in jobs:
            f.write(f"\n=== {name} ===\n");f.flush()
            try:
                result=subprocess.run([sys.executable,'-X','utf8',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
                code=result.returncode
            except Exception as exc:
                f.write(str(exc)+'\n');code=1
            f.write(f"Exit code: {code}\n");f.flush()
            failed |= code!=0
        f.write('FINAL STATUS: '+('FAILED' if failed else 'OK')+'\n')
    print(log)
    return int(failed)

if __name__=='__main__':
    sys.exit(main())
