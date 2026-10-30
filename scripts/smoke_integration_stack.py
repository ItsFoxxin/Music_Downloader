"""End-to-end checks for the already-running disposable integration stack."""
from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "integration" / ".runtime"
COMPOSE = ROOT / "integration" / "compose.yaml"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(opener, url: str, *, form: dict | None = None, body: dict | None = None,
            headers: dict | None = None):
    values = dict(headers or {})
    payload = None
    if form is not None:
        payload = urllib.parse.urlencode(form).encode()
    elif body is not None:
        payload = json.dumps(body).encode()
        values["Content-Type"] = "application/json"
    try:
        return opener.open(urllib.request.Request(url, data=payload, headers=values), timeout=15)
    except urllib.error.HTTPError as exc:
        return exc


def csrf(html: str, name: str = "csrf") -> str:
    match = re.search(rf'name="{name}" value="([^"]+)"', html)
    assert match, f"Missing {name} token"
    return match.group(1)


def compose(env: Path, *args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(env), "-f", str(COMPOSE), *args],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return result.stdout if capture else ""


def wait_for(opener, url: str, expected: int = 200, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if request(opener, url).status == expected:
                return
        except OSError:
            pass
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for {url}")


def load_env(path: Path) -> dict[str, str]:
    return dict(line.rstrip("\n").split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if line)


def main() -> None:
    env_path = RUNTIME / "integration.env"
    values = load_env(env_path)
    base = values["INTEGRATION_PUBLIC_ORIGIN"]
    plain = urllib.request.build_opener(NoRedirect())
    wait_for(plain, base + "/health")

    admin_jar = http.cookiejar.CookieJar()
    admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(admin_jar), NoRedirect())
    setup = request(admin, base + "/setup").read().decode()
    created = request(admin, base + "/setup", form={
        "csrf": csrf(setup), "bootstrap_secret": values["INTEGRATION_BOOTSTRAP_SECRET"],
        "username": "integration-admin", "display_name": "Integration Admin",
        "password": "Integration-Admin-Password-7!",
    })
    assert created.status == 303
    assert b"Your media den" in request(admin, base + "/").read()

    # One Portal session enters both real modules with no module login.
    for path in ("/music/", "/music/static/styles.css", "/media/", "/media/assets/style.css"):
        response = request(admin, base + path)
        payload = response.read()
        assert response.status == 200, (
            f"{path}: HTTP {response.status}; location={response.headers.get('Location')!r}; "
            f"body={payload[:300]!r}"
        )
    assert request(admin, base + "/api/platform/v1/session", headers={
        "X-FoxDen-Ingress": "1", "X-FoxDen-Ingress-Auth": "forged",
    }).status == 404

    # Administrator writes retain module-specific origin/CSRF protection.
    library = request(admin, base + "/music/library").read().decode()
    scan = request(admin, base + "/music/library/scans", form={"csrf_token": csrf(library, "csrf_token")},
                   headers={"Origin": base})
    assert scan.status == 303 and scan.headers["Location"].startswith("/music/library")
    media_write = request(admin, base + "/media/api/requests", body={
        "query": "Synthetic integration movie", "media_type": "Movie",
    }, headers={"Origin": base})
    assert media_write.status == 202

    # Create a restricted Portal identity and prove read/write boundaries.
    users = request(admin, base + "/admin/users").read().decode()
    assert request(admin, base + "/admin/users", form={
        "csrf": csrf(users), "username": "integration-reader", "display_name": "Integration Reader",
        "password": "Integration-Reader-Password-8!", "role": "user",
    }).status == 200
    reader_jar = http.cookiejar.CookieJar()
    reader = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(reader_jar), NoRedirect())
    login = request(reader, base + "/login").read().decode()
    signed_in = request(reader, base + "/login", form={
        "csrf": csrf(login), "username": "integration-reader",
        "password": "Integration-Reader-Password-8!",
    })
    assert signed_in.status == 303
    assert request(reader, base + "/music/").status == 200
    assert request(reader, base + "/media/api/status").status == 200
    denied = request(reader, base + "/media/api/requests", body={
        "query": "Must be denied", "media_type": "Movie",
    }, headers={"Origin": base})
    assert denied.status == 403

    # Missing modules do not take down Portal; missing auth fails protected routes closed.
    compose(env_path, "stop", "music")
    assert request(admin, base + "/").status == 200
    assert request(admin, base + "/music/").status == 503
    compose(env_path, "start", "music")
    wait_for(admin, base + "/music/")
    compose(env_path, "stop", "portal")
    assert request(admin, base + "/music/").status == 503
    compose(env_path, "start", "portal")
    wait_for(admin, base + "/")

    # Disposable SQLite and module state survive safe restarts.
    compose(env_path, "restart", "portal", "music", "music-worker", "media")
    wait_for(admin, base + "/")
    assert request(admin, base + "/media/api/requests").status == 200

    logs = compose(env_path, "logs", "--no-color", capture=True)
    for secret_name in ("INTEGRATION_PORTAL_SECRET", "INTEGRATION_BOOTSTRAP_SECRET",
                        "INTEGRATION_CSRF_SECRET", "INTEGRATION_MEDIA_TOKEN"):
        assert values[secret_name] not in logs
    print("Isolated Portal, Music, worker, Movies/TV, and Nginx end-to-end smoke passed.")


if __name__ == "__main__":
    main()
