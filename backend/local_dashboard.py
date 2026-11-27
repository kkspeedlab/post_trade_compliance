"""Local dashboard; no cloud upload or Microsoft permissions required."""
import json
import subprocess
import sys
import secrets
from datetime import date
import sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'private/reconciliation.sqlite3'
TOKEN=secrets.token_urlsafe(32)
HTML="""<!doctype html><html><head><meta charset="utf-8"><title>RM-204 Post-Trade Compliance</title><style>
body{font:15px system-ui;background:#f4f6f9;color:#203047;margin:32px}section{background:white;padding:20px;margin:18px 0;border:1px solid #dce2ea;border-radius:8px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}button{padding:9px 16px}h1{margin-bottom:4px}small{color:#657184}</style></head><body>
<small>RM-204 · Investment Controlling</small><h1>Post-Trade Compliance</h1><button onclick="load()">Refresh</button> <button onclick="runRecon(this)">Run Reconciliation</button> <label><input type="checkbox" id="openOnly" onchange="load()"> Outstanding only</label><details><summary>Local source settings</summary><label>Orders folder <input id="ordersRoot" size="90"></label><br><label>Trade history <input id="history" size="90"></label><br><label>Compliance folder <input id="archiveRoot" size="90"></label></details><pre id="log"></pre><p id="status"></p>
<section><h2>Trade reconciliation</h2><p id="summary"></p><table id="orders"></table></section>
<section><h2>Report history</h2><table id="reports"></table></section>
<section><h2>Investment Restrictions</h2><p>Pending implementation.</p></section>
<script>
const token='__TOKEN__';
async function action(payload){const r=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':token},body:JSON.stringify(payload)});const d=await r.json();document.getElementById('log').textContent=d.output;if(!r.ok)throw Error(d.output);await load()}
async function runRecon(b){b.disabled=true;try{const settings={};for(const k of ['ordersRoot','history','archiveRoot']){settings[k]=document.getElementById(k).value;localStorage.setItem(k,settings[k])}if(!confirm('Run reconciliation and archive completed reports?'))return;await action({action:'run',...settings})}catch(e){document.getElementById('status').textContent=e.message}finally{b.disabled=false}}
for(const k of ['ordersRoot','history','archiveRoot'])document.getElementById(k).value=localStorage.getItem(k)||'';
async function closeOrder(id){const reason=prompt('Closure reason (optional). Cancel to abort.');if(reason===null||!confirm('Close remaining quantity without recording execution?'))return;try{await action({action:'close',id,reason})}catch(e){document.getElementById('status').textContent=e.message}}
function table(id,headers,rows){const t=document.getElementById(id);t.replaceChildren();for(const [i,row] of [headers,...rows].entries()){const tr=t.insertRow();for(const v of row){const c=document.createElement(i?'td':'th');if(v instanceof Node)c.append(v);else c.textContent=v??'';tr.append(c)}}}
async function load(){try{const r=await fetch('/api/register');if(!r.ok)throw Error(await r.text());const d=await r.json();document.getElementById('summary').textContent=d.orders.length+' orders | '+d.orders.filter(o=>!['Fully Executed','Manually Closed'].includes(o.status)).length+' open';table('orders',['Date','Account','Bank','Instrument','Ordered','Executed','Unexecuted','Status','Order ID','Action'],d.orders.filter(o=>!document.getElementById('openOnly').checked||!['Fully Executed','Manually Closed'].includes(o.status)).map(o=>[o.day,o.account,o.bank,o.instrument,o.quantity,o.executed,o.quantity-o.executed,o.status,o.order_id,closureButton(o)]));table('reports',['Order date','Account','PDF','Available'],d.reports.map(o=>[o.day,o.account,pdfLink(o),o.available?'Yes':'No']));document.getElementById('status').textContent='Register loaded'}catch(e){document.getElementById('status').textContent=e.message}}
function closureButton(o){const b=document.createElement('button');b.textContent='Close';b.disabled=!['Partially Executed','Not Executed'].includes(o.status)||!!o.review;b.onclick=()=>closeOrder(o.order_id);return b}
function pdfLink(o){const a=document.createElement('a');a.textContent=o.pdf;if(o.available){a.href='/pdf/'+o.id;a.target='_blank';a.rel='noopener'}return a}
load()</script></body></html>"""
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/favicon.ico':
            self.send_response(204);self.end_headers();return
        if path=='/':
            data=HTML.replace('__TOKEN__',TOKEN).encode();kind='text/html; charset=utf-8'
        elif path=='/api/register':
            try:
                with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as db:
                    orders=[json.loads(r[0]) for r in db.execute('SELECT payload FROM order_status')]
                    reports=[dict(id=i,day=d,account=a,pdf=Path(p).name,available=Path(p).is_file()) for i,d,a,p in db.execute('SELECT rowid,day,account,pdf FROM report_register ORDER BY day DESC,account')]
                data=json.dumps(dict(orders=orders,reports=reports)).encode();kind='application/json'
            except Exception as exc:
                self.send_error(503,'Register unavailable');return
        elif path.startswith('/pdf/'):
            try:
                with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as db:
                    row=db.execute('SELECT pdf FROM report_register WHERE rowid=?',(int(path.split('/')[-1]),)).fetchone()
                file=Path(row[0]);assert file.suffix.lower()=='.pdf';data=file.read_bytes();kind='application/pdf'
            except Exception:
                self.send_error(404);return
        else:
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if self.path!='/api/action' or self.headers.get('X-Local-Token')!=TOKEN or self.headers.get('Origin')!='http://127.0.0.1:8765':
            self.send_error(403);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=65536: raise ValueError('Invalid request')
            d=json.loads(self.rfile.read(n))
            if d['action']=='run':
                args=['backend/run_preview.py','--orders-root',d['ordersRoot'],'--history',d['history'],'--archive-root',d['archiveRoot'],'--archive']
            elif d['action']=='close':
                args=['backend/manage_orders.py','close',d['id'],'--reason='+d.get('reason','')]
            else: raise ValueError('Unknown action')
            result=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,errors='replace')
            output=result.stdout+result.stderr
            code=200 if result.returncode==0 else 400
        except Exception as exc:
            output=str(exc);code=400
        data=json.dumps({'output':output}).encode()
        self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    print('Open http://127.0.0.1:8765')
    HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
