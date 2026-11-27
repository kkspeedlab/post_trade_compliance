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
        for row in rows:
            if not any(v is not None for v in row): continue
            d=dict(zip(headers,row)); instrument=str(d['ISIN' if u else 'Asset']).strip().upper(); key=MAP.get(instrument,instrument)
            if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{10}',key): raise ValueError('Unmapped instrument '+instrument)
            yield dict(account=account,bank=bank,day=day,source=name,original=d,instrument=instrument,key=key,side=str(d['Side' if u else 'Stex Order Group']).upper(),quantity=float(d['Quantity (shares)' if u else 'Quantity']))
def main():
    p=argparse.ArgumentParser();p.add_argument('--orders',nargs='+',type=Path,required=True);p.add_argument('--history',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--as-of',required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    orders=[o for f in a.orders for o in read_orders(f)]; rows=iter(load_workbook(a.history,read_only=True,data_only=True)['All Trades'].values); h=next(rows); trades=[dict(zip(h,r)) for r in rows]; used=set(); styles=getSampleStyleSheet(); stamp=datetime.now().strftime('%Y_%m_%d_%H.%M.%S')
    def key(o):return(o['bank'],o['account'],o['key'],o['side'])
    counts=Counter(map(key,orders))
    for o in orders:
        candidates=[(i,t) for i,t in enumerate(trades) if (t['Bank'],t['Account'],t['ISIN'],t['Buy/Sell'])==key(o) and o['day']<=str(t['Trade Date'])[:10]<=a.as_of and str(t['Reporting Date'])[:10]<=a.as_of and i not in used]
        total=sum(abs(float(t['Quantity'])) for i,t in candidates);o['matches']=[];o['review']=''
        if counts[key(o)]>1 or total>o['quantity']:o['review']='Ambiguous or excess execution; manual attribution required'
        else:
            o['matches']=[t for i,t in candidates];used.update(i for i,t in candidates)
        o['executed']=sum(abs(float(t['Quantity'])) for t in o['matches']);o['status']='Fully Executed' if o['executed']==o['quantity'] else 'Partially Executed' if o['executed'] else 'Not Executed'
    def para(v):return Paragraph(escape('' if v is None else str(v)),styles['BodyText'])
    def table(rows,widths):
        t=Table([[para(v) for v in r] for r in rows],colWidths=widths,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe5ef')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)]));return t
    styles['BodyText'].fontSize=7;styles['BodyText'].leading=9
    for account in sorted(set(o['account'] for o in orders)):
        oo=[o for o in orders if o['account']==account]; story=[Paragraph('RM-204 | Trade Reconciliation — '+account,styles['Title']),Paragraph('Report cutoff: '+a.as_of+' | Generated: '+datetime.now().strftime('%d/%m/%Y %H:%M:%S'),styles['Normal']),Spacer(1,12),Paragraph('1. Original order instructions',styles['Heading2'])]
        for bank in sorted(set(o['bank'] for o in oo)):
            bb=[o for o in oo if o['bank']==bank]; headers=list(bb[0]['original']);story.extend([Paragraph(bank+' | '+escape(bb[0]['source']),styles['Heading3']),table([headers]+[[o['original'].get(h) for h in headers] for o in bb],[740/len(headers)]*len(headers)),Spacer(1,12)])
        story.extend([PageBreak(),Paragraph('2. Post-trade results — '+account,styles['Heading2']),Paragraph('Bank evidence: '+escape(a.history.name),styles['Normal']),Spacer(1,10),table([['Bank','Instrument','Ordered','Executed','Outstanding','Status','Review']]+[[o['bank'],o['instrument'],o['quantity'],o['executed'],o['quantity']-o['executed'],o['status'],o['review']] for o in oo],[55,110,65,65,75,110,260]),Spacer(1,12),Paragraph('Individual bank execution evidence',styles['Heading3'])]); fields=['Bank','ISIN','Trade Date','Reporting Date','Settlement Date','Buy/Sell','Quantity','Price','Price Currency','Trade Reference'];story.append(table([fields]+[[t[f] for f in fields] for o in oo for t in o['matches']],[45,100,70,70,75,45,55,60,55,165]));story.append(Paragraph('Settlement dates are bank-reported; independent settlement confirmation is not inferred. Matching uses bank, account, instrument, side and dates, not a shared order ID.',styles['BodyText']));out=a.output/f'{account}_Trade_Reconciliation_{stamp}.pdf';SimpleDocTemplate(str(out),pagesize=landscape(A4),leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=35).build(story);print(account,len(oo),Counter(o['status'] for o in oo),out)
if __name__=='__main__':main()
