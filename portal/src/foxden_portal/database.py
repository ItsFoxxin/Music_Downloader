from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import uuid


SCHEMA_VERSION = "1"


class PortalStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise RuntimeError("Portal database path must not be a symlink.")
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS portal_metadata (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL, password_hash TEXT, role TEXT NOT NULL,
                    active INTEGER NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS external_identities (
                    provider TEXT NOT NULL, subject TEXT NOT NULL, user_id TEXT NOT NULL,
                    claims_json TEXT NOT NULL, updated_at INTEGER NOT NULL,
                    PRIMARY KEY(provider, subject), FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf_hash TEXT NOT NULL,
                    auth_source TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS login_limits (
                    key_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL,
                    window_started INTEGER NOT NULL, locked_until INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS oidc_flows (
                    state_hash TEXT PRIMARY KEY, nonce TEXT NOT NULL, code_verifier TEXT NOT NULL,
                    return_to TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
            """)
            stored = db.execute("SELECT value FROM portal_metadata WHERE key='schema_version'").fetchone()
            if stored is None:
                db.execute("INSERT INTO portal_metadata(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,))
                db.execute("INSERT INTO portal_metadata(key,value) VALUES('first_started_at',?)", (str(int(time.time())),))
            elif stored[0] != SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported Portal database schema {stored[0]}.")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def has_admin(self) -> bool:
        with self.connection() as db:
            return db.execute("SELECT 1 FROM users WHERE role='admin' AND active=1 LIMIT 1").fetchone() is not None

    def first_started_at(self) -> int:
        with self.connection() as db:
            return int(db.execute("SELECT value FROM portal_metadata WHERE key='first_started_at'").fetchone()[0])

    def bootstrap_used(self) -> bool:
        with self.connection() as db:
            return db.execute("SELECT 1 FROM portal_metadata WHERE key='bootstrap_used_at'").fetchone() is not None

    def claim_first_admin(self, username: str, display_name: str, password_hash: str) -> dict:
        now = int(time.time())
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                raise ValueError("Initial administrator setup is already complete.")
            if db.execute("SELECT 1 FROM portal_metadata WHERE key='bootstrap_used_at'").fetchone() is not None:
                raise ValueError("Bootstrap credentials have already been used.")
            user_id = str(uuid.uuid4())
            db.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",
                       (user_id, username, display_name, password_hash, "admin", 1, now))
            db.execute("INSERT INTO portal_metadata(key,value) VALUES('bootstrap_used_at',?)", (str(now),))
            return {"id": user_id, "username": username, "display_name": display_name, "role": "admin", "active": True}

    def create_local_user(self, username: str, display_name: str, password_hash: str, role: str) -> dict:
        if role not in {"admin", "user"}:
            raise ValueError("Unsupported role.")
        user_id, now = str(uuid.uuid4()), int(time.time())
        with self.connection() as db:
            try:
                db.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",
                           (user_id, username, display_name, password_hash, role, 1, now))
            except sqlite3.IntegrityError as exc:
                raise ValueError("That username is already in use.") from exc
        return self.user_by_id(user_id)

    def user_by_username(self, username: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return dict(row) if row else None

    def user_by_id(self, user_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def users(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT id,username,display_name,role,active,created_at FROM users ORDER BY username")]

    def update_password(self, username: str, password_hash: str) -> None:
        with self.connection() as db:
            cursor = db.execute("UPDATE users SET password_hash=? WHERE username=? AND active=1", (password_hash, username))
            if cursor.rowcount != 1:
                raise ValueError("Active local user was not found.")
            user = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            db.execute("DELETE FROM sessions WHERE user_id=?", (user[0],))

    def create_session(self, user_id: str, auth_source: str, lifetime: int) -> tuple[str, str]:
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        now = int(time.time())
        with self.connection() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (
                _hash(token), user_id, _hash(csrf), auth_source, now, now + lifetime))
        return token, csrf

    def session(self, token: str | None) -> dict | None:
        if not token:
            return None
        now = int(time.time())
        with self.connection() as db:
            row = db.execute("""SELECT s.*,u.username,u.display_name,u.role,u.active
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""", (_hash(token), now)).fetchone()
            if row is None:
                db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
                return None
            return dict(row)

    def verify_csrf(self, token: str, csrf: str | None) -> bool:
        session = self.session(token)
        return bool(session and csrf and secrets.compare_digest(session["csrf_hash"], _hash(csrf)))

    def revoke_session(self, token: str | None) -> None:
        if token:
            with self.connection() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(token),))

    def rate_limited(self, key: str) -> int:
        now = int(time.time())
        with self.connection() as db:
            row = db.execute("SELECT locked_until FROM login_limits WHERE key_hash=?", (_hash(key),)).fetchone()
            return max(0, int(row[0]) - now) if row else 0

    def record_failure(self, key: str, max_attempts: int, window_seconds: int, lock_seconds: int) -> None:
        now, key_hash = int(time.time()), _hash(key)
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM login_limits WHERE key_hash=?", (key_hash,)).fetchone()
            if row is None or now - row["window_started"] > window_seconds:
                failures, started = 1, now
            else:
                failures, started = row["failures"] + 1, row["window_started"]
            locked = now + lock_seconds if failures >= max_attempts else 0
            db.execute("INSERT OR REPLACE INTO login_limits VALUES(?,?,?,?)", (key_hash, failures, started, locked))

    def clear_failures(self, key: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM login_limits WHERE key_hash=?", (_hash(key),))

    def create_oidc_flow(self, state: str, nonce: str, verifier: str, return_to: str, lifetime: int = 300) -> None:
        now = int(time.time())
        with self.connection() as db:
            db.execute("DELETE FROM oidc_flows WHERE expires_at<=?", (now,))
            db.execute("INSERT INTO oidc_flows VALUES(?,?,?,?,?,?)",
                       (_hash(state), nonce, verifier, return_to, now, now + lifetime))

    def consume_oidc_flow(self, state: str) -> dict | None:
        now = int(time.time())
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM oidc_flows WHERE state_hash=? AND expires_at>?", (_hash(state), now)).fetchone()
            db.execute("DELETE FROM oidc_flows WHERE state_hash=?", (_hash(state),))
            return dict(row) if row else None

    def map_external_identity(self, provider: str, subject: str, username: str, display_name: str,
                              claims: dict, role: str) -> dict:
        now = int(time.time())
        safe_claims = {key: claims.get(key) for key in ("sub", "preferred_username", "name", "email", "groups") if key in claims}
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            linked = db.execute("SELECT user_id FROM external_identities WHERE provider=? AND subject=?",
                                (provider, subject)).fetchone()
            if linked:
                db.execute("UPDATE external_identities SET claims_json=?,updated_at=? WHERE provider=? AND subject=?",
                           (json.dumps(safe_claims), now, provider, subject))
                user_id = linked[0]
            else:
                candidate = username
                suffix = 1
                while db.execute("SELECT 1 FROM users WHERE username=?", (candidate,)).fetchone():
                    suffix += 1
                    candidate = f"{username}-{suffix}"
                user_id = str(uuid.uuid4())
                db.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",
                           (user_id, candidate, display_name, None, role, 1, now))
                db.execute("INSERT INTO external_identities VALUES(?,?,?,?,?)",
                           (provider, subject, user_id, json.dumps(safe_claims), now))
            row = db.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
            if row is None:
                raise ValueError("The linked Portal account is disabled.")
            return dict(row)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
