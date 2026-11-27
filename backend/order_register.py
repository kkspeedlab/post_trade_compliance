"""Independent persistent import register. No changes to source workbooks."""
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class OrderRegister:
    def __init__(self, database):
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS submissions (
            digest TEXT PRIMARY KEY, filename TEXT NOT NULL,
            bank TEXT NOT NULL, order_date TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_files (
            source_key TEXT PRIMARY KEY, digest TEXT NOT NULL
            REFERENCES submissions(digest)
        );
        """)
    def inspect(self, path, bank, order_date, source_key=None):
        path = Path(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_key = source_key or str(path.resolve())
        prior = self.db.execute("SELECT digest FROM source_files WHERE source_key=?", (source_key,)).fetchone()
        if prior and prior[0] != digest:
            return "REVISION", digest
        if self.db.execute("SELECT 1 FROM submissions WHERE digest=?", (digest,)).fetchone():
            return "DUPLICATE", digest
        if self.db.execute("SELECT 1 FROM submissions WHERE filename=? AND bank=? AND order_date=?", (path.name, bank, order_date)).fetchone():
            return "REVISION", digest
        return "NEW", digest
    def record_validated(self, path, bank, order_date, source_key=None):
        """Call only after successful workbook validation. Revisions require review."""
        path = Path(path)
        state, digest = self.inspect(path, bank, order_date, source_key)
        if state == "REVISION":
            raise ValueError("Changed order workbook requires explicit review")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO submissions VALUES (?,?,?,?,?)",
                (digest,path.name,bank,order_date,datetime.now(timezone.utc).isoformat()))
            self.db.execute("INSERT OR IGNORE INTO source_files VALUES (?,?)",
                (source_key or str(path.resolve()),digest))
        return state, digest
    def close(self):
        self.db.close()
