"""Build and exercise the Portal as a non-root, read-only container."""
from __future__ import annotations

import json
from pathlib import Path
import secrets
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "fox-den-portal:phase1a-smoke"


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    return result.stdout.strip() if capture else ""


def main() -> None:
    name = "foxden-portal-smoke-" + secrets.token_hex(4)
    portal_secret = secrets.token_urlsafe(40)
    assertion_secret = secrets.token_urlsafe(40)
    bootstrap = secrets.token_urlsafe(40)
    try:
        run("docker", "build", "-t", IMAGE, str(ROOT))
        run("docker", "run", "-d", "--name", name, "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "--tmpfs", "/config:rw,noexec,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0770",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "-e", f"PORTAL_SECRET_KEY={portal_secret}",
            "-e", f"PORTAL_INTERNAL_ASSERTION_SECRET={assertion_secret}",
            "-e", f"PORTAL_BOOTSTRAP_SECRET={bootstrap}",
            "-e", "PORTAL_COOKIE_SECURE=false", IMAGE)
        for _ in range(30):
            try:
                output = run("docker", "exec", name, "python", "-c",
                             "import json,urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8020/health',timeout=2))['status'])",
                             capture=True)
                if output == "healthy":
                    break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise RuntimeError("Portal container did not become healthy")
        inspected = json.loads(run("docker", "inspect", name, capture=True))[0]
        assert inspected["Config"]["User"] == "foxden:foxden"
        assert inspected["HostConfig"]["ReadonlyRootfs"] is True
        assert inspected["HostConfig"]["CapDrop"] == ["ALL"]
        print("Portal container smoke passed: non-root, read-only, healthy")
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Portal container smoke failed: {type(exc).__name__}", file=sys.stderr)
        raise
