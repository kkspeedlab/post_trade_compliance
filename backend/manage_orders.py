"""Local operator controls for the reconciliation register."""
import argparse
import json
from datetime import date
from pathlib import Path
from incremental import Cache

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,default=Path('private/reconciliation.sqlite3'))
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('list')
    close=sub.add_parser('close')
    close.add_argument('order_id')
    close.add_argument('--date',type=date.fromisoformat,default=date.today())
    close.add_argument('--reason',default='')
    a=p.parse_args()
    if not a.database.is_file():
        p.error('Run reconciliation first')
    c=Cache(a.database)
    c.closures()
    rows={oid:json.loads(payload) for oid,payload in c.db.execute('SELECT id,payload FROM order_status')}
    if a.action=='list':
        for oid,o in rows.items():
            if o['status'] not in ('Fully Executed','Manually Closed'):
                print(oid,o['day'],o['account'],o['bank'],o['instrument'],o['status'],'Outstanding:',o['quantity']-o['executed'],o['review'])
        print('Open orders:',sum(o['status'] not in ('Fully Executed','Manually Closed') for o in rows.values()))
        return
    o=rows.get(a.order_id)
    if not o or o['status'] not in ('Partially Executed','Not Executed') or o['review']:
        p.error('Order not eligible for closure; ambiguous attribution must be resolved separately')
    if not date.fromisoformat(o['day'])<=a.date<=date.today():
        p.error('Closure date must be between order date and today')
    with c.db:
        c.db.execute('INSERT INTO closures VALUES (?,?,?)',(a.order_id,a.date.isoformat(),a.reason))
    print('Closure recorded. Run reconciliation to update the report. Executed quantity is unchanged.')

if __name__=='__main__':
    main()
