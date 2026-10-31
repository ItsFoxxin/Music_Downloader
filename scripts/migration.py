#!/usr/bin/env python3
"""Non-destructive inventory, backup, verification, and restore rehearsal tools."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from foxden import ConfigError, load_env, validate

PATH_ROLES = {
    "portal-config": "PORTAL_CONFIG_PATH",
    "music-config": "MUSIC_CONFIG_PATH",
    "music-staging": "MUSIC_STAGING_PATH",
    "music-downloads": "MUSIC_DOWNLOAD_PATH",
    "music-library": "MUSIC_LIBRARY_PATH",
    "media-config": "MEDIA_CONFIG_PATH",
    "media-library": "MEDIA_LIBRARY_PATH",
    "torrent-data": "TORRENT_DATA_PATH",
    "qbittorrent-config": "QBIT_CONFIG_PATH",
    "gluetun-config": "GLUETUN_CONFIG_PATH",
}

BACKUP_ROLES = {
    "portal-config",
    "music-config",
    "music-staging",
    "music-downloads",
    "media-config",
    "qbittorrent-config",
    "gluetun-config",
}

LARGE_DATA_ROLES = {"music-library", "media-library", "torrent-data"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(values: dict[str, str]) -> dict[str, object]:
    entries = []
    for role, key in PATH_ROLES.items():
        raw = values.get(key, "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        entry: dict[str, object] = {"role": role, "variable": key, "path": str(path), "exists": path.exists()}
        if path.is_dir() and role not in LARGE_DATA_ROLES:
            files = 0
            bytes_total = 0
            for root, dirs, names in os.walk(path, followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
                for name in names:
                    candidate = Path(root) / name
                    try:
                        if candidate.is_file() and not candidate.is_symlink():
                            files += 1
                            bytes_total += candidate.stat().st_size
                    except OSError:
                        entry["scan_warning"] = "One or more entries could not be inspected."
            entry.update(files=files, bytes=bytes_total)
        elif path.is_dir():
            entry["content_scan"] = "skipped-large-data-root"
        entries.append(entry)
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "entries": entries,
        "notes": [
            "Inventory does not inspect secret contents.",
            "Running container state and open SQLite transactions require a separate operator check.",
        ],
    }


def backup_sources(values: dict[str, str]) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for role, key in PATH_ROLES.items():
        if role not in BACKUP_ROLES:
            continue
        raw = values.get(key, "").strip()
        if raw:
            path = Path(raw).expanduser().resolve()
            if path.exists():
                sources[role] = path
    return sources


def readiness(values: dict[str, str], mode: str) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    try:
        validate(mode, values)
        checks.append({"name": "configuration", "status": "pass"})
    except (ConfigError, OSError, ValueError) as exc:
        checks.append({"name": "configuration", "status": "fail", "detail": str(exc)})
    report = inventory(values)
    missing = [str(entry["role"]) for entry in report["entries"] if not entry["exists"]]
    checks.append({
        "name": "configured-paths",
        "status": "pass" if not missing else "fail",
        "detail": "all configured paths exist" if not missing else "missing: " + ", ".join(missing),
    })
    for name in ("production writers stopped", "final backup verified", "rollback rehearsal passed"):
        checks.append({"name": name, "status": "manual-approval-required"})
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "ready_for_cutover": all(item["status"] == "pass" for item in checks),
        "checks": checks,
        "inventory": report,
    }


def create_backup(values: dict[str, str], destination: Path, *, execute: bool, writers_stopped: bool) -> Path | None:
    sources = backup_sources(values)
    if not sources:
        raise ConfigError("No existing state directories were configured.")
    destination = destination.expanduser().resolve()
    for source in sources.values():
        if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ConfigError("Backup destination must not overlap a source directory.")
    print("Backup source plan:")
    for role, source in sources.items():
        print(f"  {role}: {source}")
    if not execute:
        print("Dry run only. Stop all writers and repeat with --writers-stopped --execute.")
        return None
    if not writers_stopped:
        raise ConfigError("Refusing backup without --writers-stopped confirmation.")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = destination / f"foxden-state-{stamp}.tar.gz"
    with tarfile.open(archive, "x:gz", format=tarfile.PAX_FORMAT) as bundle:
        for role, source in sources.items():
            bundle.add(source, arcname=role, recursive=True)
    digest = _sha256(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Created verified backup archive {archive}")
    return archive


def verify_backup(archive: Path) -> bool:
    archive = archive.resolve()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    if not archive.is_file() or not checksum.is_file():
        raise ConfigError("Archive or sidecar checksum is missing.")
    expected = checksum.read_text(encoding="ascii").split()[0]
    actual = _sha256(archive)
    if actual != expected:
        raise ConfigError("Backup checksum does not match.")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise ConfigError("Backup archive is empty.")
        for member in members:
            if Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                raise ConfigError("Backup contains an unsafe path.")
    print(f"Backup verified: {archive.name} ({len(members)} entries)")
    return True


def restore_rehearsal(archive: Path, destination: Path, *, execute: bool) -> None:
    verify_backup(archive)
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ConfigError("Restore destination must be empty.")
    print(f"Restore target: {destination}")
    if not execute:
        print("Dry run only. Repeat with --execute to restore into this isolated destination.")
        return
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(destination, filter="data")
    print("Restore rehearsal completed. This does not authorize a production cutover.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fox Den Media migration rehearsal tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--env", type=Path, required=True)
    inv.add_argument("--output", type=Path, required=True)
    ready = sub.add_parser("readiness")
    ready.add_argument("--env", type=Path, required=True)
    ready.add_argument("--mode", choices=("music", "media", "full-external", "full-managed"), required=True)
    ready.add_argument("--output", type=Path, required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--env", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--writers-stopped", action="store_true")
    backup.add_argument("--execute", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore-rehearsal")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            report = inventory(load_env(args.env.resolve()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(f"Wrote read-only inventory to {args.output}")
        elif args.command == "readiness":
            report = readiness(load_env(args.env.resolve()), args.mode)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(f"Wrote migration readiness report to {args.output}")
        elif args.command == "backup":
            create_backup(load_env(args.env.resolve()), args.destination, execute=args.execute, writers_stopped=args.writers_stopped)
        elif args.command == "verify":
            verify_backup(args.archive)
        else:
            restore_rehearsal(args.archive, args.destination, execute=args.execute)
        return 0
    except (ConfigError, OSError, tarfile.TarError, ValueError) as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
