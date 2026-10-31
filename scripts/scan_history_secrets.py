#!/usr/bin/env python3
"""Fail closed on common committed-secret shapes without printing secret values."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BLOB = 2 * 1024 * 1024
SENSITIVE_NAMES = re.compile(r"(^|/)(\.env|[^/]+\.(?:pem|key|p12|sqlite|sqlite3|db))$", re.I)
PATTERNS = {
    "private-key-block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----"),
    "github-token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    "openai-key": re.compile(rb"\bsk-[A-Za-z0-9_-]{24,}\b"),
}
ASSIGNMENT = re.compile(
    rb"(?mi)^\s*(?:WIREGUARD_PRIVATE_KEY|JELLYFIN_API_KEY|QBIT_PASSWORD|PORTAL_SECRET_KEY|PORTAL_BOOTSTRAP_SECRET|APP_TOKEN)\s*=\s*([^\r\n#]+)"
)
PLACEHOLDERS = {b"", b"ci-unused", b"unused", b"changeme", b"change_me", b"example", b"test", b"redacted"}


def main() -> int:
    listing = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT, text=True)
    paths: dict[str, str] = {}
    for line in listing.splitlines():
        object_id, _, path = line.partition(" ")
        if path and object_id not in paths:
            paths[object_id] = path
    check_input = "".join(f"{object_id}\n" for object_id in paths)
    checked = subprocess.check_output(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=ROOT, input=check_input, text=True,
    )
    blobs: list[str] = []
    for line in checked.splitlines():
        object_id, object_type, size = line.split()
        if object_type == "blob" and int(size) <= MAX_BLOB:
            blobs.append(object_id)
    payload = subprocess.check_output(
        ["git", "cat-file", "--batch"], cwd=ROOT,
        input="".join(f"{object_id}\n" for object_id in blobs).encode("ascii"),
    )
    findings: list[tuple[str, str]] = []
    offset = 0
    for expected in blobs:
        header_end = payload.index(b"\n", offset)
        object_id, object_type, raw_size = payload[offset:header_end].decode("ascii").split()
        if object_id != expected or object_type != "blob":
            raise RuntimeError("Unexpected git cat-file batch response.")
        size = int(raw_size)
        start = header_end + 1
        content = payload[start:start + size]
        offset = start + size + 1
        path = paths[object_id]
        if SENSITIVE_NAMES.search(path) and not any(token in path.lower() for token in ("example", "fixture", "test")):
            findings.append((path, "sensitive-filename"))
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((path, label))
        assignment_fixture = path.lower().endswith(".md") or any(
            token in path.lower() for token in ("example", "fixture", "test")
        )
        if not assignment_fixture:
            for match in ASSIGNMENT.finditer(content):
                value = match.group(1).strip().strip(b"'\"").lower()
                if value not in PLACEHOLDERS and not value.startswith((b"${", b"/run/secrets/")):
                    findings.append((path, "populated-sensitive-assignment"))
    unique = sorted(set(findings))
    if unique:
        for path, label in unique:
            print(f"Potential secret: {label} in {path}")
        return 1
    print(f"Scanned {len(blobs)} reachable blobs; no configured secret signatures were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
