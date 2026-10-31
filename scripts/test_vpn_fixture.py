#!/usr/bin/env python3
"""Prove a torrent-client fixture cannot egress outside its VPN namespace."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "tests" / "fixtures" / "vpn" / "compose.yaml"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", "compose", "-f", str(COMPOSE), *args], cwd=ROOT, text=True, check=check)


def main() -> int:
    try:
        run("up", "-d", "--wait")
        result = run(
            "exec", "-T", "torrent-client", "sh", "-c",
            "wget -T 3 -q -O /dev/null http://1.1.1.1 && exit 42 || exit 0",
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit("Torrent fixture unexpectedly reached an external address without VPN networking.")
        print("Synthetic VPN failure remained fail-closed: torrent namespace had no independent egress.")
        return 0
    finally:
        run("down", "--volumes", "--remove-orphans", check=False)


if __name__ == "__main__":
    raise SystemExit(main())
