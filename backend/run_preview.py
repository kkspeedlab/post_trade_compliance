"""Local preview: reads synced files, never writes to compliance folders."""
import argparse
import hashlib
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from settings import eligible_order_date

def discover(root, cutoff):
    seen = set()
    names = {}
    result = []
    for month in sorted(root.iterdir()):
        if not month.is_dir() or not re.fullmatch(r"20\d{2}-\d{2}-[A-Za-z]{3}", month.name):
            continue
        for path in sorted(month.glob("*.xlsx")):
            m = re.fullmatch(r"EQ_Upload.*?_(\d{8})\.xlsx", path.name, re.I)
            fmt = "%Y%m%d"
            if not m:
                m = re.fullmatch(r"MultiStexTemplate(\d{6}).*\.xlsx", path.name, re.I)
                fmt = "%y%m%d"
            if not m:
                continue
            day = datetime.strptime(m.group(1), fmt).date()
            if not eligible_order_date(day, cutoff):
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            key = path.name.casefold()
            if key in names and names[key] != digest:
                raise ValueError("Conflicting versions: " + path.name)
            names[key] = digest
            if digest not in seen:
                seen.add(digest)
                result.append(path)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--orders-root", type=Path, required=True)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    p.add_argument("--output", type=Path, default=Path("preview_reports"))
    p.add_argument("--list-only", action="store_true")
    p.add_argument("--archive-root", type=Path)
    p.add_argument("--archive", action="store_true", help="Save completed reports to the compliance archive")
    a = p.parse_args()
    if a.archive and not a.archive_root:
        p.error("--archive requires --archive-root")
    if not a.orders_root.is_dir() or not a.history.is_file():
        p.error("Order folder or bank history is missing")
    files = discover(a.orders_root, a.as_of)
    print("Eligible unique workbooks:", len(files), flush=True)
    for f in files:
        print(f, flush=True)
    if a.list_only:
        return
    if not files and not (a.archive and Path('private/reconciliation.sqlite3').is_file()):
        return
    # Preview output only; do not use the live compliance archive.
    if any(part.casefold() == "rm-204 investment controlling" for part in a.output.resolve().parts):
        p.error("Preview must not write into the compliance archive")
    if a.archive_root and not a.archive_root.is_dir():
        p.error("Compliance archive folder missing")
    extra = ["--archive-root", str(a.archive_root)] if a.archive_root else []
    if a.archive:
        extra.append("--archive")
    subprocess.run([sys.executable, str(Path(__file__).with_name("post_trade_reconcile.py")),
        "--orders", *map(str, files), "--history", str(a.history),
        "--as-of", a.as_of.isoformat(), "--output", str(a.output), *extra], check=True)

if __name__ == "__main__":
    main()
