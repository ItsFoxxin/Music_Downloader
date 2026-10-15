"""Linux CI smoke tests against built images and the real Compose gateway.

Uses isolated temporary storage; never starts a VPN or a torrent client.
Stable mode additionally validates, imports, audits, and restarts persisted media.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    version = (root / "VERSION").read_text().strip()
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="foxden-ci-") as directory:
        data = Path(directory)
        env = os.environ.copy()
        for key in ("CONFIG_PATH", "STAGING_PATH", "DOWNLOAD_INBOX_PATH", "MUSIC_PATH",
                    "MEDIA_CONFIG_PATH", "TORRENT_STAGING_PATH", "MEDIA_PATH",
                    "TORRENT_CONFIG_PATH", "GLUETUN_CONFIG_PATH", "BROWSER_CONFIG_PATH"):
            path = data / key.lower()
            path.mkdir()
            env[key] = str(path)
        key_file = data / "unused-vpn-key"
        key_file.write_text("CI does not start VPN containers\n")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env.update(PUID=str(os.getuid()), PGID=str(os.getgid()), APP_TOKEN=token,
                   CSRF_SECRET=secrets.token_urlsafe(32), JELLYFIN_API_KEY="ci-unused",
                   WIREGUARD_PUBLIC_KEY="ci-unused", WIREGUARD_ENDPOINT_IP="192.0.2.10",
                   WIREGUARD_PRIVATE_KEY_FILE=str(key_file), WEB_BIND_IP="127.0.0.1",
                   WEB_PORT=str(port), COOKIE_SECURE="false", SETTLE_SECONDS="0",
                   QBIT_URL="http://127.0.0.1:9", QBIT_PUBLIC_URL="", FULL_DECODE="true")
        compose = ["docker", "compose", "--project-name", "foxden-ci-" + secrets.token_hex(4),
                   "--env-file", "/dev/null", "-f", str(root / "compose.yaml")]

        def run(*command, capture=False, check=True):
            return subprocess.run([*compose, *command], cwd=root, env=env, check=check,
                                  text=True, capture_output=capture, timeout=900)

        base = f"http://127.0.0.1:{port}"
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def request(path, body=None, *, headers=None, expected=200):
            request_headers = dict(headers or {})
            payload = None
            if body is not None:
                payload = json.dumps(body).encode()
                request_headers["Content-Type"] = "application/json"
            req = urllib.request.Request(base + path, data=payload, headers=request_headers)
            try:
                response = client.open(req, timeout=10)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                content = response.read()
                assert response.status == expected, f"{path}: HTTP {response.status}, expected {expected}"
                return content

        def api(path, body=None, *, expected=200):
            return json.loads(request("/transfers/api/" + path, body,
                                     headers={"X-Foxden-Request": "1"}, expected=expected))

        def wait_health():
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    request("/transfers/health")
                    return
                except (OSError, AssertionError):
                    time.sleep(1)
            raise AssertionError("Media did not become healthy through the gateway")

        def wait_job(ident):
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                job = next(j for j in api("jobs") if j["id"] == ident)
                if job["status"] == "succeeded":
                    return job
                assert job["status"] not in {"failed", "interrupted"}, job.get("error")
                time.sleep(.5)
            raise AssertionError("Media job timed out")

        try:
            run("build", "media", "web")
            # --no-deps intentionally excludes the browser and real VPN/client.
            run("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "web", "worker", "media", "gateway")
            run("exec", "-T", "gateway", "nginx", "-t")
            wait_health()
            request("/transfers/api/status", expected=401)
            assert b'id="login-form"' in request("/")  # gateway redirects anonymous music visitors
            request("/transfers/api/session", {}, headers={"Authorization": "Bearer " + token})
            assert api("status")["version"] == version
            media_request = api("requests", {"query": "CI Requested Movie (2026)",
                                              "media_type": "Movie"}, expected=202)
            assert media_request["status"] == "waiting_for_user"
            assert any(item["id"] == media_request["id"] for item in api("requests"))
            assert b'id="app-version"' in request("/transfers/")
            request("/transfers/assets/app.js")
            assert b"Fox Den" in request("/")  # real music web application through shared session
            request("/transfers/api/logout", {}, expected=403)  # cookie writes need CSRF header
            for service in ("media", "web", "worker"):
                uid = run("exec", "-T", service, "id", "-u", capture=True).stdout.strip()
                assert uid == env["PUID"] and uid != "0", f"Unexpected user in {service}"
            run("exec", "-T", "media", "python", "-c",
                "import os; assert not os.access('/staging', os.W_OK), 'staging is writable'")
            if args.strict:
                source = Path(env["TORRENT_STAGING_PATH"]) / "CI Sample"
                source.mkdir()
                # Generate through the image's real FFmpeg into writable temporary storage.
                run("exec", "-T", "media", "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=blue:s=64x48:r=10", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "0.5", "-c:v", "mpeg4", "-c:a", "aac", "/tmp/ci-sample.mp4")
                run("cp", "media:/tmp/ci-sample.mp4", str(source / "sample.mp4"))
                before = hashlib.sha256((source / "sample.mp4").read_bytes()).hexdigest()
                validation = wait_job(api("validate", {"source": "CI Sample"}, expected=202)["id"])
                assert validation["result"]["files"][0]["media"]["validation"] == "full decode"
                payload = {"validation_id": validation["id"], "category": "Movies", "name": "CI Sample"}
                imported = wait_job(api("import", payload, expected=202)["id"])
                destination = Path(env["MEDIA_PATH"]) / "Movies" / "CI Sample" / "sample.mp4"
                assert hashlib.sha256(destination.read_bytes()).hexdigest() == before
                assert hashlib.sha256((source / "sample.mp4").read_bytes()).hexdigest() == before
                api("import", payload, expected=400)  # no overwrite
                audited = wait_job(api(f"library/{imported['id']}/audit", {}, expected=202)["id"])
                assert not audited["result"]["issues"]
                run("restart", "media")
                wait_health()
                assert any(item["id"] == imported["id"] for item in api("library")), "Import lost after restart"
                assert any(item["id"] == media_request["id"] for item in api("requests")), "Request lost after restart"
            api("logout", {})
            request("/transfers/api/status", expected=401)
            print("PASS: built containers, gateway, shared auth, version, request persistence, permissions" +
                  (", full decode, import, audit, no overwrite, source preservation, restart persistence" if args.strict else ""))
        except BaseException:
            run("logs", "--no-color", "--tail", "100", check=False)
            raise
        finally:
            run("down", "--volumes", "--remove-orphans", check=False)


if __name__ == "__main__":
    main()
