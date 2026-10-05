import json
import sqlite3
import threading
import time
import uuid


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as c:
            c.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, payload TEXT NOT NULL,
                    result TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS imports (
                    id TEXT PRIMARY KEY, created REAL NOT NULL, destination TEXT UNIQUE NOT NULL,
                    manifest TEXT NOT NULL, checked REAL, health TEXT NOT NULL);
            """)
            # A process crash never silently retries a write. Recovery checks the on-disk receipt.
            c.execute("UPDATE jobs SET status='interrupted', error='Server restarted; inspect the result before retrying.', updated=? WHERE status='running'", (time.time(),))

    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def decode(row):
        if row is None:
            return None
        d = dict(row)
        for key in ("payload", "result", "manifest"):
            if key in d and d[key] is not None:
                d[key] = json.loads(d[key])
        return d

    def enqueue(self, kind, payload):
        ident = uuid.uuid4().hex
        now = time.time()
        with self.lock, self.connect() as c:
            if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 100:
                raise ValueError("Queue is full. Wait for existing jobs to finish.")
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)",
                      (ident, kind, "queued", now, now, json.dumps(payload)))
        return self.job(ident)

    def job(self, ident):
        with self.connect() as c:
            return self.decode(c.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone())

    def jobs(self):
        with self.connect() as c:
            return [self.decode(r) for r in c.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 200")]

    def claim(self):
        with self.lock, self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            c.execute("UPDATE jobs SET status='running', updated=? WHERE id=?", (time.time(), row["id"]))
            return self.decode(row)

    def finish(self, ident, result=None, error=None):
        with self.connect() as c:
            c.execute("UPDATE jobs SET status=?,updated=?,result=?,error=? WHERE id=?",
                      ("failed" if error else "succeeded", time.time(), json.dumps(result), error, ident))

    def imports(self):
        with self.connect() as c:
            return [self.decode(r) for r in c.execute("SELECT * FROM imports ORDER BY created DESC")]

    def record_import(self, ident, destination, manifest):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO imports VALUES (?,?,?,?,?,?)",
                      (ident, time.time(), destination, json.dumps(manifest), time.time(), "verified"))

    def health(self, ident, status):
        with self.connect() as c:
            c.execute("UPDATE imports SET checked=?,health=? WHERE id=?", (time.time(), status, ident))
