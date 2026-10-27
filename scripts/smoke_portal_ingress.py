"""Exercise the future Portal-owned Nginx ingress with no modules running."""
from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
PORTAL_IMAGE = "fox-den-portal:ingress-smoke"


def run(*args: str, capture: bool = False, check: bool = True) -> str:
    result = subprocess.run(args, cwd=ROOT, check=check, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    return result.stdout.strip() if capture else ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def response(opener, url: str, *, data: dict | None = None, headers: dict | None = None):
    payload = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=payload, headers=headers or {})
    try:
        return opener.open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        return exc


def main() -> None:
    suffix = secrets.token_hex(4)
    network = f"foxden-ingress-{suffix}"
    portal = f"foxden-portal-{suffix}"
    ingress = f"foxden-ingress-{suffix}"
    bootstrap = secrets.token_urlsafe(40)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    try:
        run("docker", "build", "-t", PORTAL_IMAGE, str(ROOT / "portal"))
        run("docker", "network", "create", network)
        run("docker", "run", "-d", "--name", portal, "--network", network,
            "--network-alias", "portal", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "--tmpfs", "/config:rw,noexec,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0770",
            "-e", f"PORTAL_PUBLIC_URL={base}", "-e", "PORTAL_COOKIE_SECURE=false",
            "-e", f"PORTAL_SECRET_KEY={secrets.token_urlsafe(40)}",
            "-e", f"PORTAL_INTERNAL_ASSERTION_SECRET={secrets.token_urlsafe(40)}",
            "-e", f"PORTAL_BOOTSTRAP_SECRET={bootstrap}",
            "-e", "PORTAL_MODULES_JSON=[]", PORTAL_IMAGE)
        run("docker", "run", "-d", "--name", ingress, "--network", network,
            "--user", "101:101", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "-p", f"127.0.0.1:{port}:8080",
            "-v", f"{(ROOT / 'gateway' / 'portal-ingress.conf').resolve()}:/etc/nginx/nginx.conf:ro",
            "nginx:stable-alpine", "nginx", "-g", "daemon off;")
        run("docker", "exec", ingress, "nginx", "-t")

        plain = urllib.request.build_opener(NoRedirect())
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                with response(plain, base + "/health") as result:
                    if result.status == 200:
                        break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise AssertionError("Portal did not become available through ingress")

        # Client identity headers are stripped before Portal sees the request.
        with response(plain, base + "/health", headers={"X-FoxDen-Identity": "forged"}) as result:
            assert result.status == 200
        with response(plain, base + "/media/") as result:
            assert result.status == 302 and result.headers["Location"] == "/login"

        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with response(client, base + "/setup") as result:
            setup = result.read().decode()
        csrf = re.search(r'name="csrf" value="([^"]+)"', setup)
        assert csrf, "Portal setup CSRF token missing"
        with response(client, base + "/setup", data={
            "csrf": csrf.group(1), "bootstrap_secret": bootstrap,
            "username": "ci-admin", "display_name": "CI Admin",
            "password": "CI-Portal-Password-7!",
        }) as result:
            assert result.status == 200 and b"Your media den" in result.read()
        with response(client, base + "/api/platform/v1/session") as result:
            assert result.status == 204 and result.read() == b""

        # Auth succeeds, then unavailable optional modules fail closed and do not
        # affect the Portal root.
        for route in ("/music/", "/media/", "/server-browser/"):
            with response(client, base + route) as result:
                assert result.status == 503 and result.read() == b"Module unavailable\n"
        with response(client, base + "/") as result:
            assert result.status == 200 and b"Your media den" in result.read()

        inspected = json.loads(run("docker", "inspect", ingress, capture=True))[0]
        assert inspected["Config"]["User"] == "101:101"
        assert inspected["HostConfig"]["ReadonlyRootfs"] is True
        assert inspected["HostConfig"]["CapDrop"] == ["ALL"]
        print("Portal ingress smoke passed: independent Portal, protected routes, missing-module isolation")
    finally:
        subprocess.run(["docker", "rm", "-f", ingress, portal], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "network", "rm", network], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Portal ingress smoke failed: {type(exc).__name__}", file=sys.stderr)
        raise
