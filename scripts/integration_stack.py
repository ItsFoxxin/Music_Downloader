"""Prepare and control the disposable 0.4.1 integration stack."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "integration" / ".runtime"
COMPOSE = ROOT / "integration" / "compose.yaml"
RECORDED_MUSIC_COMMIT = "b4bbffbb2a739a8b78ec6b194416b8d4fb5e09ea"


def run(*args: str, cwd: Path = ROOT, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def verify_music(source: Path) -> None:
    source = source.resolve()
    if not (source / ".git").exists():
        raise SystemExit("Music source must be a dedicated Git checkout or worktree.")
    run("git", "merge-base", "--is-ancestor", RECORDED_MUSIC_COMMIT, "HEAD", cwd=source)
    status = run("git", "status", "--short", cwd=source, capture=True)
    if status:
        raise SystemExit("Music integration checkout must be committed and clean before container testing.")


def prepare(source: Path, port: int) -> Path:
    verify_music(source)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        RUNTIME.chmod(0o700)
    for child in RUNTIME.iterdir():
        if child.is_file():
            child.unlink()
    portal_image = "foxden-portal:0.4.1-integration"
    run("docker", "build", "-t", portal_image, str(ROOT / "portal"))
    run("docker", "run", "--rm", "--user", "0", "-v", f"{RUNTIME.resolve()}:/keys",
        portal_image, "foxden-identity-keygen", "--private", "/keys/private.pem",
        "--public", "/keys/public.json", "--kid", "integration-1")
    ingress_secret = secrets.token_urlsafe(48)
    (RUNTIME / "ingress-auth").write_text(ingress_secret, encoding="utf-8")
    template = (ROOT / "gateway" / "portal-ingress.conf").read_text(encoding="utf-8")
    (RUNTIME / "portal-ingress.conf").write_text(
        template.replace("__PORTAL_INGRESS_AUTH_SECRET__", ingress_secret), encoding="utf-8")
    run("docker", "run", "--rm", "--user", "0", "-v", f"{RUNTIME.resolve()}:/keys",
        portal_image, "chown", "10001:10001", "/keys/private.pem", "/keys/ingress-auth")
    env = RUNTIME / "integration.env"
    values = {
        "MUSIC_SOURCE_PATH": source.resolve().as_posix(),
        "INTEGRATION_PORT": str(port),
        "INTEGRATION_PUBLIC_ORIGIN": f"http://127.0.0.1:{port}",
        "INTEGRATION_PORTAL_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_BOOTSTRAP_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_CSRF_SECRET": secrets.token_urlsafe(48),
        "INTEGRATION_MEDIA_TOKEN": secrets.token_urlsafe(48),
    }
    env.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    if os.name != "nt":
        env.chmod(0o600)
    print(f"Disposable stack prepared at http://127.0.0.1:{port}")
    print(f"Bootstrap secret is stored in ignored runtime file: {env}")
    return env


def compose(env: Path, *args: str) -> None:
    run("docker", "compose", "--env-file", str(env), "-f", str(COMPOSE), *args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("up", "down", "config"))
    parser.add_argument("--music-source", type=Path)
    parser.add_argument("--port", type=int, default=18080)
    options = parser.parse_args()
    env = RUNTIME / "integration.env"
    if options.action == "up":
        if not options.music_source:
            parser.error("up requires --music-source pointing to the isolated authoritative Music checkout")
        env = prepare(options.music_source, options.port)
        compose(env, "up", "--build", "-d", "--wait")
    elif options.action == "config":
        if not env.is_file():
            raise SystemExit("Run the up preparation first.")
        compose(env, "config", "--quiet")
    else:
        if env.is_file():
            compose(env, "down", "--volumes", "--remove-orphans")
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)
        print("Disposable integration containers, volumes, and test secrets removed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Integration command failed with exit code {exc.returncode}.", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
