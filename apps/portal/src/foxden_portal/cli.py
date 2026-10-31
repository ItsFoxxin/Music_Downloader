from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .auth import AuthService
from .config import Settings
from .database import PortalStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Portal account recovery")
    sub = parser.add_subparsers(dest="command", required=True)
    reset = sub.add_parser("set-password", help="Reset a local password and revoke that account's sessions")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password-file", type=Path,
                       help="Read the new password from a protected file; interactive input is used if omitted")
    bootstrap = sub.add_parser("reset-bootstrap-window",
                               help="Re-open first-run setup only when the database contains no users")
    bootstrap.add_argument("--confirm-no-users", action="store_true", required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = PortalStore(settings.database_path)
    store.initialize()
    auth = AuthService(settings, store)
    if args.command == "reset-bootstrap-window":
        if store.users():
            raise SystemExit("Bootstrap cannot be reset after any account exists. Use set-password recovery.")
        import time
        with store.connection() as db:
            db.execute("UPDATE portal_metadata SET value=? WHERE key='first_started_at'", (str(int(time.time())),))
            db.execute("DELETE FROM portal_metadata WHERE key='bootstrap_used_at'")
        print("Bootstrap window reset. Restart with a newly rotated PORTAL_BOOTSTRAP_SECRET file.")
        return
    if args.password_file:
        if args.password_file.is_symlink():
            raise SystemExit("Password file must not be a symlink.")
        try:
            password = args.password_file.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise SystemExit("Password file is not readable.") from exc
    else:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")
    auth.set_password(args.username, password)
    print("Password updated and existing sessions revoked.")


if __name__ == "__main__":
    main()
