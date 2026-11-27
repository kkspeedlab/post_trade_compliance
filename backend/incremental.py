"""Local SQLite cache; changed matching groups are always recomputed."""
import hashlib
import json
import sqlite3
from pathlib import Path

def encode(value):
    return json.dumps(value, default=str, sort_keys=True, ensure_ascii=False)

def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()

class Cache:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS matching_cache (
            group_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, results TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS report_register (
            day TEXT, account TEXT, fingerprint TEXT, pdf TEXT,
            PRIMARY KEY(day, account, fingerprint)
        );
        CREATE TABLE IF NOT EXISTS workbook_register (
            name TEXT PRIMARY KEY, fingerprint TEXT NOT NULL
        );
        """)
    def validate_workbooks(self, paths):
        current = {p.name.casefold(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        for name, fingerprint in current.items():
            old = self.db.execute("SELECT fingerprint FROM workbook_register WHERE name=?", (name,)).fetchone()
            if old and old[0] != fingerprint:
                raise ValueError("Order workbook revision requires review: " + name)
        return current
    def save_workbooks(self, current):
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO workbook_register VALUES (?,?)", current.items())
    def get(self, key, fingerprint):
        row = self.db.execute("SELECT results FROM matching_cache WHERE group_key=? AND fingerprint=?", (encode(key), fingerprint)).fetchone()
        return json.loads(row[0]) if row else None
    def put(self, key, fingerprint, results):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO matching_cache VALUES (?,?,?)", (encode(key), fingerprint, encode(results)))
    def report(self, day, account, fingerprint, path):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO report_register VALUES (?,?,?,?)", (day, account, fingerprint, str(path)))
    def existing(self, day, account, fingerprint):
        row = self.db.execute("SELECT pdf FROM report_register WHERE day=? AND account=? AND fingerprint=?", (day, account, fingerprint)).fetchone()
        return Path(row[0]) if row and Path(row[0]).is_file() else None
