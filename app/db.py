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
                CREATE TABLE IF NOT EXISTS media_requests (
                    id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
                    media_type TEXT NOT NULL, query TEXT NOT NULL, title TEXT NOT NULL,
                    status TEXT NOT NULL, torrent_hash TEXT, validation_id TEXT,
                    import_id TEXT, acquisition_id TEXT, error TEXT);
            """)
            request_columns = {r[1] for r in c.execute("PRAGMA table_info(media_requests)")}
            if "acquisition_id" not in request_columns:
                c.execute("ALTER TABLE media_requests ADD COLUMN acquisition_id TEXT")
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

    def create_request(self, media_type, query, title, torrent_hash=None, acquisition_id=None):
        ident = uuid.uuid4().hex
        now = time.time()
        status = "acquiring" if torrent_hash else "waiting_for_user"
        with self.connect() as c:
            c.execute("""INSERT INTO media_requests
                      (id,created,updated,media_type,query,title,status,torrent_hash,
                       validation_id,import_id,acquisition_id,error)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (ident, now, now, media_type, query, title, status,
                       torrent_hash, None, None, acquisition_id, None))
        return self.media_request(ident)

    def media_request(self, ident):
        with self.connect() as c:
            row = c.execute("SELECT * FROM media_requests WHERE id=?", (ident,)).fetchone()
            return dict(row) if row else None

    def media_requests(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM media_requests ORDER BY created DESC LIMIT 200")]

    def update_request(self, ident, **fields):
        allowed = {"status", "torrent_hash", "validation_id", "import_id", "acquisition_id", "error"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.media_request(ident)
        updates["updated"] = time.time()
        columns = ",".join(f"{key}=?" for key in updates)
        with self.connect() as c:
            c.execute(f"UPDATE media_requests SET {columns} WHERE id=?",
                      (*updates.values(), ident))
        return self.media_request(ident)

    def request_for_validation(self, validation_id):
        with self.connect() as c:
            row = c.execute("SELECT * FROM media_requests WHERE validation_id=?",
                            (validation_id,)).fetchone()
            return dict(row) if row else None
