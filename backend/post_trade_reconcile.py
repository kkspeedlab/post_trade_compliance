import argparse,re
from pathlib import Path
from datetime import datetime
from collections import Counter
from openpyxl import load_workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4,landscape
from xml.sax.saxutils import escape
MAP={'UXZ6 INDEX':'ZZ9892006716','UXF7 INDEX':'ZZ9892006748','UXG7 INDEX':'ZZ9892006751'}
def read_orders(path):
    name=path.name; u=name.lower().startswith('eq_upload'); bank='UBS' if u else 'HSBC'
    if not u and not name.lower().startswith('multistextemplate'): raise ValueError(name)
    m=re.search(r'(?<!\d)(\d{8}|\d{6})(?!\d)',name); day=datetime.strptime(m[1],'%Y%m%d' if len(m[1])==8 else '%y%m%d').date().isoformat()
    for s in load_workbook(path,read_only=True,data_only=True):
        account=s.title.upper();
        if account=='TOTALS': continue
        if account not in ('ADV','ELE','ENV','JOINT','COMPANY'): raise ValueError('Unknown sheet '+s.title)
        rows=iter(s.values)
        if u: next(rows);next(rows)
        headers=next(rows)
        for row_number,row in enumerate(rows,start=4 if u else 2):
            if not any(v is not None for v in row): continue
            d=dict(zip(headers,row))
            raw=d.get('ISIN' if u else 'Asset')
            quantity=d.get('Quantity (shares)' if u else 'Quantity')
            side=d.get('Side' if u else 'Stex Order Group')
            instrument=str(raw or '').strip().upper()
            missing=instrument in ('','NONE','N/A')
            if missing and (quantity is None or str(quantity).strip() in ('','0','0.0')) and not str(side or '').strip():
                continue
            key=MAP.get(instrument,instrument)
            if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{10}',key):
                raise ValueError(f'{name} | sheet {s.title} | row {row_number}: Unmapped or missing instrument {instrument!r}; quantity={quantity!r}; side={side!r}')
            yield dict(source_row=row_number,account=account,bank=bank,day=day,source=name,original=d,instrument=instrument,key=key,side=str(d['Side' if u else 'Stex Order Group']).upper(),quantity=float(d['Quantity (shares)' if u else 'Quantity']))
def main():
    p=argparse.ArgumentParser();p.add_argument('--orders',nargs='*',type=Path,required=True);p.add_argument('--history',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--as-of',required=True);p.add_argument('--archive-root',type=Path);p.add_argument('--archive',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.archive and (not a.archive_root or not a.archive_root.is_dir()):
        p.error('--archive requires an existing archive root')
    orders=[o for f in a.orders for o in read_orders(f)]; rows=iter(load_workbook(a.history,read_only=True,data_only=True)['All Trades'].values); h=next(rows); trades=[dict(zip(h,r)) for r in rows]; used=set(); styles=getSampleStyleSheet(); stamp=datetime.now().strftime('%Y_%m_%d_%H.%M.%S')
    def key(o):return(o['bank'],o['account'],o['key'],o['side'])
    from incremental import Cache, digest
    cache=Cache(Path('private')/'reconciliation.sqlite3') if a.archive else None
    current=cache.validate_workbooks(a.orders) if cache else {}
    for o in orders:
        o['order_id']=digest([o['source'].casefold(),o['account'],o['source_row']])[:24]
    if cache:
        orders=cache.retained_orders(orders,a.as_of)
    closures=cache.closures() if cache else {}
    groups={}
    for o in orders:
        groups.setdefault(key(o),[]).append(o)
    trade_groups={}
    for t in trades:
        if str(t['Trade Date'])[:10]<=a.as_of and str(t['Reporting Date'])[:10]<=a.as_of:
            trade_groups.setdefault((t['Bank'],t['Account'],t['ISIN'],t['Buy/Sell']),[]).append(t)
    reused=0; recalculated=0
    for k,group in groups.items():
        group=sorted(group,key=lambda x:x['day'])
        group_trades=trade_groups.get(k,[])
        fp=digest(['matching-v2',group,group_trades,{o['order_id']:closures[o['order_id']] for o in group if o['order_id'] in closures}])
        cached=cache.get(k,fp) if cache else None
        if cached is not None:
            for o,result in zip(group,cached):
                o.update(result)
            reused+=len(group)
            continue
        used=set()
        counts=Counter((key(o),o['day']) for o in group)
        for o in group:
            siblings=[x for x in group if x is not o and key(x)==key(o)]
            later_dates=[x['day'] for x in siblings if x['day']>o['day']]
            next_day=min(later_dates) if later_dates else None
            prior_open=any(x['day']<o['day'] and x.get('status')!='Fully Executed' and not (x['order_id'] in closures and closures[x['order_id']][0]<o['day'] and not x.get('review')) for x in siblings)
            candidates=[(i,t) for i,t in enumerate(group_trades) if (t['Bank'],t['Account'],t['ISIN'],t['Buy/Sell'])==key(o) and o['day']<=str(t['Trade Date'])[:10]<=a.as_of and (next_day is None or str(t['Trade Date'])[:10]<next_day) and str(t['Reporting Date'])[:10]<=a.as_of and i not in used]
            total=sum(abs(float(t['Quantity'])) for i,t in candidates);o['matches']=[];o['review']=''
            if counts[(key(o),o['day'])]>1 or prior_open or total>o['quantity']:
                o['review']='Ambiguous or excess execution; manual attribution required'
            else:
                o['matches']=[t for i,t in candidates];used.update(i for i,t in candidates)
            o['executed']=sum(abs(float(t['Quantity'])) for t in o['matches']);o['status']='Fully Executed' if o['executed']==o['quantity'] else 'Partially Executed' if o['executed'] else 'Not Executed'
        recalculated+=len(group)
        if cache:
            cache.put(k,fp,[{f:o[f] for f in ('matches','review','executed','status')} for o in group])
    print('INCREMENTAL | reused orders:',reused,'| recalculated orders:',recalculated)
    for o in orders:
        closure=closures.get(o['order_id'])
        if closure and closure[0]<=a.as_of and o['status']!='Fully Executed' and not o['review']:
            o['status']='Manually Closed'
            o['review']='Closed '+closure[0]+(' — '+closure[1] if closure[1] else '')
        if o['status'] not in ('Fully Executed','Manually Closed'):
            print('OPEN',o['order_id'],o['day'],o['account'],o['bank'],o['instrument'],o['status'],o['quantity']-o['executed'])
    if cache:
        cache.save_workbooks(current)
        cache.save_status(orders)
    def para(v):return Paragraph(escape('' if v is None else str(v)),styles['BodyText'])
    def table(rows,widths):
        t=Table([[para(v) for v in r] for r in rows],colWidths=widths,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe5ef')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)]));return t
    styles['BodyText'].fontSize=7;styles['BodyText'].leading=9
    for day,account in sorted(set((o['day'],o['account']) for o in orders)):
        oo=[o for o in orders if o['account']==account and o['day']==day]
        report_fp=digest(['report-v1',[{k:v for k,v in o.items() if k not in ('order_id','source_row')} for o in oo]])
        if cache:
            registered=cache.existing(day,account,report_fp)
            if registered:
                print(day,account,'SKIP — registered report:',registered.name)
                continue
        if a.archive_root:
            from archive_check import archived_report
            existing=archived_report(a.archive_root,day,account,oo)
            if existing:
                if cache: cache.report(day,account,report_fp,existing)
                print(day,account,'SKIP — existing archived report:',existing.name)
                continue
        if a.archive and any(o['status'] not in ('Fully Executed','Manually Closed') for o in oo):
            print(day,account,'DEFER — outstanding or ambiguous orders; use preview mode')
            continue
        story=[Paragraph('RM-204 | Trade Reconciliation — '+account,styles['Title']),Paragraph('Order date: '+day+' | Report cutoff: '+a.as_of+' | Generated: '+datetime.now().strftime('%d/%m/%Y %H:%M:%S'),styles['Normal']),Spacer(1,12),Paragraph('1. Original order instructions',styles['Heading2'])]
        for bank,source in sorted(set((o['bank'],o['source']) for o in oo)):
            bb=[o for o in oo if o['bank']==bank and o['source']==source]; headers=list(bb[0]['original']);story.extend([Paragraph(bank+' | '+escape(bb[0]['source']),styles['Heading3']),table([headers]+[[o['original'].get(h) for h in headers] for o in bb],[740/len(headers)]*len(headers)),Spacer(1,12)])
        story.extend([PageBreak(),Paragraph('2. Post-trade results — '+account,styles['Heading2']),Paragraph('Bank evidence: '+escape(a.history.name),styles['Normal']),Spacer(1,10),table([['Bank','Order date','Instrument','Ordered','Executed','Outstanding','Status','Review']]+[[o['bank'],o['day'],o['instrument'],o['quantity'],o['executed'],o['quantity']-o['executed'],o['status'],o['review']] for o in oo],[45,65,100,55,55,65,100,255]),Spacer(1,12),Paragraph('Individual bank execution evidence',styles['Heading3'])]); fields=['Bank','ISIN','Trade Date','Reporting Date','Settlement Date','Buy/Sell','Quantity','Price','Price Currency','Trade Reference'];story.append(table([fields]+[[t[f] for f in fields] for o in oo for t in o['matches']],[45,100,70,70,75,45,55,60,55,165]));story.append(Paragraph('Settlement dates are bank-reported; independent settlement confirmation is not inferred. Matching uses bank, account, instrument, side and dates, not a shared order ID.',styles['BodyText']));folder=a.output/day;folder.mkdir(parents=True,exist_ok=True);out=folder/f'{account}_Trade_Reconciliation_{stamp}.pdf';SimpleDocTemplate(str(out),pagesize=landscape(A4),leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=35).build(story)
        if a.archive:
            import shutil
            import time
            month=datetime.fromisoformat(day)
            month_name=month.strftime('%Y-%m-')+'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[month.month-1]
            target=a.archive_root/month_name/'Trade Reconciliation'/account
            target.mkdir(parents=True,exist_ok=True)
            # Keep approved naming convention and never overwrite an archived PDF.
            while True:
                dest=target/f"{account}_Trade_Reconciliation_{datetime.now().strftime('%Y_%m_%d_%H.%M.%S')}.pdf"
                try:
                    handle=dest.open('xb')
                except FileExistsError:
                    time.sleep(1)
                    continue
                try:
                    with handle, out.open('rb') as source:
                        shutil.copyfileobj(source,handle)
                except Exception:
                    dest.unlink(missing_ok=True)
                    raise
                break
            if cache: cache.report(day,account,report_fp,dest)
            print(day,account,'ARCHIVED',dest)
        else:
            print(day,account,len(oo),Counter(o['status'] for o in oo),out)
if __name__=='__main__':main()
