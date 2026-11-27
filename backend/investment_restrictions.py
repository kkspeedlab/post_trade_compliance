"""Daily RM-204 investment restrictions; independent of trading activity."""
import argparse
import hashlib
import json
import math
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

ACCOUNTS=('ADV','ELE','ENV','JOINT','COMPANY')
CLASSES=('Equities incl. Commodities','Fixed Income - Bonds','Hedge Funds','Money Markets')
MONTHS='Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()

def rows(w,s):
    it=iter(w[s].values)
    for r in it:
        if r[0]=='Account':
            return [dict(zip(r,x)) for x in it if x[0] is not None]
    raise ValueError('Missing headers: '+s)

def one(rs,account,field=None,value=None):
    found=[r for r in rs if str(r['Account']).upper()==account and (field is None or r[field]==value)]
    if len(found)!=1: raise ValueError(f'Expected one row: {account} {value}')
    return found[0]

def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):
        raise ValueError('Missing or invalid numeric restriction value')
    return float(x)

def check(name,actual,lo,hi,source=None):
    actual,lo,hi=map(number,(actual,lo,hi))
    if lo>hi: raise ValueError('Invalid limits: '+name)
    status='PASS' if lo<=actual<=hi else 'FAIL'
    if source is not None and source!=status: raise ValueError('Source status mismatch: '+name)
    return [name,actual,lo,hi,status]

def extract(path,day):
    with path.open('rb') as f:
        w=load_workbook(f,data_only=True,read_only=True)
        try:
            info={r[0]:r[1] for r in w['Source Info'].values if r[0]}
            if str(info['Valuation Date'])!=day.strftime('%Y%m%d'): raise ValueError('Valuation date mismatch')
            a=rows(w,'Allocation'); d=rows(w,'Derivatives allocation'); c=rows(w,'Currency Allocation')
            result={}
            for account in ACCOUNTS:
                checks=[]
                for name in CLASSES:
                    r=one(a,account,'Asset Class',name)
                    if r['Status'] not in ('PASS','FAIL'): raise ValueError('Missing allocation status')
                    checks.append(check(name,r['Combined % NAV'],r['Min %'],r['Max %'],r['Status']))
                r=one(d,account)
                if r['Status'] not in ('PASS','FAIL') or number(r['Account NAV EUR'])<=0: raise ValueError('Invalid derivative check')
                checks.append(check('Derivatives gross notional',r['Exposure % NAV'],0,r['Limit %'],r['Status']))
                eur=one(c,account,'Currency','EUR')
                total=one(c,account,'Currency','TOTAL')
                if abs(number(total['Combined % NAV'])-1)>1e-6: raise ValueError('Currency total not 100%')
                checks.append(check('Foreign currencies',1-number(eur['Combined % NAV']),0,.7))
                result[account]=checks
            return result
        finally: w.close()

def render(path,account,day,checks,now):
    styles=getSampleStyleSheet()
    overall='FAIL' if any(r[-1]=='FAIL' for r in checks) else 'PASS'
    story=[Paragraph('RM-204 | Investment Restrictions',styles['Title']),
           Paragraph(f'{account} | Valuation date: {day}',styles['Normal']),
           Paragraph('Generated: '+now.strftime('%d/%m/%Y %H:%M:%S'),styles['Normal']),Spacer(1,14),
           Paragraph('Overall result: '+overall,styles['Heading2']),
           Paragraph('Restriction checks',styles['Heading2'])]
    table=Table([['Restriction','Actual','Min.','Max.','Status']]+[[n,f'{v:.2%}',f'{lo:.2%}',f'{hi:.2%}',s] for n,v,lo,hi,s in checks],colWidths=[205,70,65,65,65])
    commands=[('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2e8f0')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce2ea'))]
    for i,r in enumerate(checks,1): commands.append(('TEXTCOLOR',(-1,i),(-1,i),colors.HexColor('#187447' if r[-1]=='PASS' else '#b91c1c')))
    table.setStyle(TableStyle(commands));story.append(table)
    SimpleDocTemplate(str(path),pagesize=A4).build(story)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--allocation-root',type=Path,required=True)
    p.add_argument('--archive-root',type=Path)
    p.add_argument('--archive',action='store_true')
    p.add_argument('--start',type=date.fromisoformat,default=date(2026,11,26))
    p.add_argument('--as-of',type=date.fromisoformat,default=date.today())
    p.add_argument('--output',type=Path,default=Path('restriction_previews'))
    a=p.parse_args()
    if not a.allocation_root.is_dir(): p.error('Allocation folder missing')
    if a.archive and (not a.archive_root or not a.archive_root.is_dir()): p.error('Archive root missing')
    if a.archive_root and a.output.resolve().is_relative_to(a.archive_root.resolve()): p.error('Preview output must be outside archive')
    files={}
    for f in a.allocation_root.rglob('*.xlsx'):
        m=re.fullmatch(r'Combined_Daily_Allocation_(\d{8})\.xlsx',f.name,re.I)
        if not m: continue
        day=datetime.strptime(m[1],'%Y%m%d').date()
        if not a.start<=day<=a.as_of: continue
        if day in files and hashlib.sha256(f.read_bytes()).digest()!=hashlib.sha256(files[day].read_bytes()).digest(): raise ValueError('Conflicting allocation files: '+str(day))
        files[day]=f
    if not files: print('WAIT — no eligible allocation workbooks');return
    db=None
    if a.archive:
        Path('private').mkdir(exist_ok=True)
        db=sqlite3.connect('private/investment_restrictions.sqlite3')
        db.execute('CREATE TABLE IF NOT EXISTS reports (day TEXT, account TEXT, fingerprint TEXT, pdf TEXT, PRIMARY KEY(day,account))')
    for day,path in sorted(files.items()):
        results=extract(path,day)
        for account,checks in results.items():
            fp=hashlib.sha256(json.dumps(checks).encode()).hexdigest()
            if db:
                prior=db.execute('SELECT fingerprint,pdf FROM reports WHERE day=? AND account=?',(str(day),account)).fetchone()
                if prior and prior[0]==fp and Path(prior[1]).is_file(): print(day,account,'SKIP — unchanged');continue
            now=datetime.now()
            folder=a.output/str(day)
            folder.mkdir(parents=True,exist_ok=True)
            name=f"{account}_Investment_Restrictions_{now.strftime('%Y_%m_%d_%H.%M.%S')}.pdf"
            out=folder/name
            render(out,account,day,checks,now)
            if db:
                target=a.archive_root/(day.strftime('%Y-%m-')+MONTHS[day.month-1])/'Investment Restrictions'/account
                target.mkdir(parents=True,exist_ok=True)
                dest=target/name
                with dest.open('xb') as f: f.write(out.read_bytes())
                with db: db.execute('INSERT OR REPLACE INTO reports VALUES (?,?,?,?)',(str(day),account,fp,str(dest.resolve())))
                out=dest
            print(day,account,'FAIL' if any(r[-1]=='FAIL' for r in checks) else 'PASS',out)
    if db: db.close()

if __name__=='__main__': main()
