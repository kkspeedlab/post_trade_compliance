"""Read existing compliance PDFs without modifying them."""
import re
from pathlib import Path
from datetime import date
from pypdf import PdfReader

def archived_report(root, day, account, orders):
    if not root or not orders or any(o['status'] != 'Fully Executed' or o['review'] for o in orders):
        return None
    month = date.fromisoformat(day)
    folder = Path(root) / (month.strftime('%Y-%m-') + ('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[month.month-1])) / 'Trade Reconciliation'
    if not folder.is_dir():
        return None
    refs = [str(t.get('Trade Reference') or '').strip() for o in orders for t in o['matches']]
    if not refs or any(not x for x in refs) or len(set(refs)) != len(refs):
        return None
    def compact(s):
        return re.sub(r'\s+', '', str(s)).casefold()
    for path in sorted(folder.glob(f'{account}_Trade_Reconciliation_*.pdf')):
        try:
            raw = '\n'.join(p.extract_text() or '' for p in PdfReader(path).pages)
        except Exception as exc:
            print('Archive PDF unreadable:', path.name, str(exc))
            continue
        txt = compact(raw)
        # Require all original source names, all unique execution references,
        # the original order date, and the exact number of fully executed rows.
        if not all(compact(o['source']) in txt for o in orders):
            continue
        if not all(compact(ref) in txt for ref in refs):
            continue
        if not any(compact(d) in txt for d in (day, month.strftime('%d/%m/%Y'), month.strftime('%Y%m%d'))):
            continue
        if len(re.findall(r'fully\s+executed', raw, re.I)) != len(orders):
            continue
        # Require exact execution evidence as well: each reference must appear
        # on a line with the bank-reported quantity and price. Fail closed for
        # older layouts where PDF extraction cannot establish this.
        lines = raw.splitlines()
        def evidence(t):
            ref = compact(t['Trade Reference'])
            def numeric(line, value):
                try:
                    n = float(value)
                except (ValueError, TypeError):
                    return False
                return any(float(x) == n for x in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])', line))
            return any(ref in compact(line) and numeric(line, t['Quantity']) and numeric(line, t['Price']) for line in lines)
        if not all(evidence(t) for o in orders for t in o['matches']):
            continue
        return path
    return None
