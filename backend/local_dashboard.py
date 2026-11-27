"""Local dashboard; no cloud upload or Microsoft permissions required."""
import json
import sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'private/reconciliation.sqlite3'
HTML="""<!doctype html><html><head><meta charset="utf-8"><title>RM-204 Post-Trade Compliance</title><style>
body{font:15px system-ui;background:#f4f6f9;color:#203047;margin:32px}section{background:white;padding:20px;margin:18px 0;border:1px solid #dce2ea;border-radius:8px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}button{padding:9px 16px}h1{margin-bottom:4px}small{color:#657184}</style></head><body>
<small>RM-204 · Investment Controlling</small><h1>Post-Trade Compliance</h1><button onclick="load()">Refresh</button><p id="status"></p>
<section><h2>Trade reconciliation</h2><p id="summary"></p><table id="orders"></table></section>
<section><h2>Report history</h2><table id="reports"></table></section>
<section><h2>Investment Restrictions</h2><p>Pending implementation.</p></section>
<script>
function table(id,headers,rows){const t=document.getElementById(id);t.replaceChildren();for(const [i,row] of [headers,...rows].entries()){const tr=t.insertRow();for(const v of row){const c=document.createElement(i?'td':'th');c.textContent=v??'';tr.append(c)}}}
async function load(){try{const r=await fetch('/api/register');if(!r.ok)throw Error(await r.text());const d=await r.json();document.getElementById('summary').textContent=d.orders.length+' orders | '+d.orders.filter(o=>!['Fully Executed','Manually Closed'].includes(o.status)).length+' open';table('orders',['Date','Account','Bank','Instrument','Ordered','Executed','Unexecuted','Status','Order ID'],d.orders.map(o=>[o.day,o.account,o.bank,o.instrument,o.quantity,o.executed,o.quantity-o.executed,o.status,o.order_id]));table('reports',['Order date','Account','PDF','Available'],d.reports.map(o=>[o.day,o.account,o.pdf,o.available?'Yes':'No']));document.getElementById('status').textContent='Register loaded'}catch(e){document.getElementById('status').textContent=e.message}}
load()</script></body></html>"""
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/':
            data=HTML.encode();kind='text/html; charset=utf-8'
        elif self.path=='/api/register':
            try:
                with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as db:
                    orders=[json.loads(r[0]) for r in db.execute('SELECT payload FROM order_status')]
                    reports=[dict(day=d,account=a,pdf=Path(p).name,available=Path(p).is_file()) for d,a,p in db.execute('SELECT day,account,pdf FROM report_register ORDER BY day DESC,account')]
                data=json.dumps(dict(orders=orders,reports=reports)).encode();kind='application/json'
            except Exception as exc:
                self.send_error(503,'Register unavailable');return
        else:
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    print('Open http://127.0.0.1:8765')
    HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
