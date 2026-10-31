#!/usr/bin/env python3
"""Validated, environment-driven entry point for Fox Den Media deployments."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "compose.yaml"
GATEWAY_TEMPLATE = ROOT / "infra" / "gateway" / "portal-ingress.conf"

MODES = {
    "music": {"profiles": ("music",), "modules": {"music"}},
    "media": {"profiles": ("media",), "modules": {"media"}},
    "full-external": {"profiles": ("music", "media"), "modules": {"music", "media"}},
    "full-managed": {"profiles": ("music", "media", "managed"), "modules": {"music", "media"}},
}
CORE_PATHS = ("FOXDEN_SECRETS_DIR", "FOXDEN_RUNTIME_DIR", "PORTAL_CONFIG_PATH")
MUSIC_PATHS = ("MUSIC_CONFIG_PATH", "MUSIC_STAGING_PATH", "MUSIC_DOWNLOAD_PATH", "MUSIC_LIBRARY_PATH")
MEDIA_PATHS = ("MEDIA_CONFIG_PATH", "MEDIA_LIBRARY_PATH", "TORRENT_DATA_PATH")
MANAGED_PATHS = ("QBIT_CONFIG_PATH", "GLUETUN_CONFIG_PATH")
SECRET_FILES = ("portal-secret", "portal-bootstrap", "ingress-auth", "identity-private.pem", "identity-public.json")
MUSIC_SECRET_FILES = ("music-csrf",)
MEDIA_SECRET_FILES = ("media-app-token", "qbit-password")


class ConfigError(RuntimeError):
    pass


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ConfigError(f"Environment file does not exist: {path}")
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"{path}:{line_number}: expected NAME=value")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if not key.replace("_", "").isalnum() or key[:1].isdigit():
            raise ConfigError(f"{path}:{line_number}: invalid variable name")
        values[key] = value
    return values


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value or value.startswith("CHANGE_ME"):
        raise ConfigError(f"Set {key} in the environment file.")
    return value


def _url(values: dict[str, str], key: str, *, https_only: bool = False) -> None:
    parsed = urlparse(_required(values, key))
    allowed = {"https"} if https_only else {"http", "https"}
    if parsed.scheme not in allowed or not parsed.netloc or parsed.username or parsed.password:
        raise ConfigError(f"{key} must be a valid {'HTTPS' if https_only else 'HTTP(S)'} URL without credentials.")


def _resources(values: dict[str, str]) -> None:
    for key, value in values.items():
        if key.endswith("_CPUS") and value.strip():
            try:
                if float(value) <= 0:
                    raise ValueError
            except ValueError as exc:
                raise ConfigError(f"{key} must be a positive CPU count.") from exc
        if key.endswith("_MEMORY_LIMIT") and value.strip():
            if not re.fullmatch(r"[1-9][0-9]*(?:[kKmMgGtT](?:[bB])?)?", value.strip()):
                raise ConfigError(f"{key} must be a positive Docker memory value such as 512m or 2g.")


def _paths(values: dict[str, str], keys: tuple[str, ...], *, create: bool = False) -> list[Path]:
    resolved: list[Path] = []
    for key in keys:
        path = Path(_required(values, key)).expanduser()
        if not path.is_absolute():
            raise ConfigError(f"{key} must be an absolute host path: {path}")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ConfigError(f"{key} is not an existing directory: {path}")
        required_access = os.R_OK | os.X_OK
        if key != "TORRENT_DATA_PATH":
            required_access |= os.W_OK
        if not os.access(path, required_access):
            expectation = "readable" if key == "TORRENT_DATA_PATH" else "readable and writable"
            raise ConfigError(f"{key} must be {expectation} by the deployment UID/GID: {path}")
        resolved.append(path.resolve())
    if len(set(resolved)) != len(resolved):
        raise ConfigError("Configured storage roles must use distinct directories.")
    return resolved


def _secret(path: Path, *, allow_empty: bool = False, private: bool = True) -> None:
    if not path.is_file():
        raise ConfigError(f"Required secret file is missing: {path.name}")
    if not allow_empty and not path.read_bytes().strip():
        raise ConfigError(f"Required secret file is empty: {path.name}")
    if private and os.name != "nt" and path.stat().st_mode & 0o077:
        raise ConfigError(f"Secret file permissions are too broad; require mode 0600: {path.name}")


def validate(mode: str, values: dict[str, str], *, browser: bool = False, create_paths: bool = False) -> None:
    definition = MODES[mode]
    _resources(values)
    _url(values, "FOXDEN_PUBLIC_ORIGIN")
    for key in ("FOXDEN_PUID", "FOXDEN_PGID", "FOXDEN_PORT"):
        value = int(_required(values, key))
        if value <= 0 or (key == "FOXDEN_PORT" and value > 65535):
            raise ConfigError(f"{key} is outside its valid range.")
    all_paths = _paths(values, CORE_PATHS, create=create_paths)
    if "music" in definition["modules"]:
        all_paths += _paths(values, MUSIC_PATHS, create=create_paths)
        _required(values, "MUSICBRAINZ_CONTACT")
    if "media" in definition["modules"]:
        all_paths += _paths(values, MEDIA_PATHS, create=create_paths)
    if mode == "full-managed":
        all_paths += _paths(values, MANAGED_PATHS, create=create_paths)
        for key in ("WIREGUARD_ADDRESSES", "WIREGUARD_PUBLIC_KEY", "WIREGUARD_ENDPOINT_IP"):
            _required(values, key)
    elif "media" in definition["modules"]:
        _url(values, "QBIT_URL")
    if values.get("JELLYFIN_URL", "").strip():
        _url(values, "JELLYFIN_URL")
    if browser:
        all_paths += _paths(values, ("BROWSER_CONFIG_PATH",), create=create_paths)
        if "music" not in definition["modules"]:
            raise ConfigError("The contained browser currently requires a Music deployment mode.")
    for index, first in enumerate(all_paths):
        for second in all_paths[index + 1:]:
            if first == second or first in second.parents or second in first.parents:
                raise ConfigError("Host storage roles must be distinct, non-overlapping directories.")

    secret_dir = Path(values["FOXDEN_SECRETS_DIR"]).resolve()
    for name in SECRET_FILES:
        _secret(secret_dir / name, private=name != "identity-public.json")
    if "music" in definition["modules"]:
        for name in MUSIC_SECRET_FILES:
            _secret(secret_dir / name)
        if values.get("JELLYFIN_URL", "").strip():
            _secret(secret_dir / "jellyfin-api-key")
    if "media" in definition["modules"]:
        for name in MEDIA_SECRET_FILES:
            _secret(secret_dir / name)
    if mode == "full-managed":
        _secret(secret_dir / "wireguard-private-key")

    try:
        modules = json.loads(_required(values, "PORTAL_MODULES_JSON"))
    except json.JSONDecodeError as exc:
        raise ConfigError("PORTAL_MODULES_JSON must be valid JSON.") from exc
    ids = {item.get("id") for item in modules if isinstance(item, dict)}
    if ids != definition["modules"]:
        raise ConfigError(f"PORTAL_MODULES_JSON must enable exactly: {sorted(definition['modules'])}")

    auth_mode = values.get("PORTAL_AUTH_MODE", "local").strip().lower()
    if auth_mode not in {"local", "oidc", "hybrid"}:
        raise ConfigError("PORTAL_AUTH_MODE must be local, oidc, or hybrid.")
    if auth_mode in {"oidc", "hybrid"}:
        _url(values, "PORTAL_OIDC_ISSUER", https_only=True)
        _required(values, "PORTAL_OIDC_CLIENT_ID")
        _secret(secret_dir / "oidc-client-secret")

    for key, value in values.items():
        if key.endswith("_IMAGE") and (value.endswith(":latest") or value == "latest"):
            raise ConfigError(f"{key} must use a pinned tag or digest, not latest.")


def initialize(values: dict[str, str], *, create_paths: bool) -> None:
    secret_dir = Path(_required(values, "FOXDEN_SECRETS_DIR")).expanduser()
    runtime_dir = Path(_required(values, "FOXDEN_RUNTIME_DIR")).expanduser()
    if not secret_dir.is_absolute() or not runtime_dir.is_absolute():
        raise ConfigError("Secret and runtime directories must be absolute paths.")
    secret_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for name in ("portal-secret", "portal-bootstrap", "ingress-auth", "music-csrf", "media-app-token"):
        target = secret_dir / name
        if not target.exists():
            target.write_text(secrets.token_urlsafe(48), encoding="utf-8")
            os.chmod(target, 0o600)
    sys.path.insert(0, str(ROOT / "apps" / "portal" / "src"))
    from foxden_identity import generate_key_files
    private = secret_dir / "identity-private.pem"
    public = secret_dir / "identity-public.json"
    if private.exists() != public.exists():
        raise ConfigError("Identity private/public files must either both exist or both be absent.")
    if not private.exists():
        generate_key_files(private, public, kid=values.get("PORTAL_IDENTITY_SIGNING_KID", "foxden-portal-1"))
        os.chmod(private, 0o600)
        os.chmod(public, 0o644)
    for optional in ("qbit-password", "wireguard-private-key", "jellyfin-api-key", "oidc-client-secret"):
        target = secret_dir / optional
        if not target.exists():
            target.touch(mode=0o600)
    if create_paths:
        keys = list(CORE_PATHS[2:]) + list(MUSIC_PATHS) + list(MEDIA_PATHS) + list(MANAGED_PATHS) + ["BROWSER_CONFIG_PATH"]
        for key in keys:
            raw = values.get(key, "").strip()
            if raw:
                path = Path(raw).expanduser()
                if not path.is_absolute():
                    raise ConfigError(f"{key} must be absolute before it can be created.")
                path.mkdir(parents=True, exist_ok=True)
    print(f"Initialized secret and runtime material under {secret_dir.parent}; secret values were not printed.")


def render_gateway(values: dict[str, str]) -> Path:
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"]).resolve()
    runtime_dir = Path(values["FOXDEN_RUNTIME_DIR"]).resolve()
    ingress_secret = (secret_dir / "ingress-auth").read_text(encoding="utf-8").strip()
    if len(ingress_secret) < 32:
        raise ConfigError("ingress-auth must contain at least 32 characters.")
    rendered = GATEWAY_TEMPLATE.read_text(encoding="utf-8").replace("__PORTAL_INGRESS_AUTH_SECRET__", ingress_secret)
    if ingress_secret not in rendered:
        raise ConfigError("Gateway template did not contain the expected secret placeholder.")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    target = runtime_dir / "nginx.conf"
    temporary = runtime_dir / ".nginx.conf.tmp"
    temporary.write_text(rendered, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(target)
    return target


def compose_command(mode: str, env_path: Path, *, browser: bool, action: str) -> list[str]:
    profiles = list(MODES[mode]["profiles"])
    if browser:
        profiles.append("browser")
    command = ["docker", "compose", "--env-file", str(env_path), "-f", str(COMPOSE)]
    for profile in profiles:
        command += ["--profile", profile]
    command.append(action)
    if action == "up":
        command.append("-d")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(prog="foxden", description="Fox Den Media deployment control")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create local secret material without overwriting existing files")
    init.add_argument("--env", type=Path, required=True)
    init.add_argument("--create-paths", action="store_true")
    for name in ("validate", "config", "deploy", "stop"):
        command = sub.add_parser(name)
        command.add_argument("mode", choices=MODES)
        command.add_argument("--env", type=Path, required=True)
        command.add_argument("--browser", action="store_true")
        if name in {"deploy", "stop"}:
            command.add_argument("--execute", action="store_true", help="actually invoke Docker Compose")
    args = parser.parse_args()
    try:
        values = load_env(args.env.resolve())
        if args.command == "init":
            initialize(values, create_paths=args.create_paths)
            return 0
        validate(args.mode, values, browser=args.browser)
        gateway = render_gateway(values)
        action = {"validate": "config", "config": "config", "deploy": "up", "stop": "down"}[args.command]
        command = compose_command(args.mode, args.env.resolve(), browser=args.browser, action=action)
        redacted = " ".join(command)
        print(f"Configuration valid for {args.mode}; rendered gateway at {gateway}.")
        print(redacted)
        if args.command in {"deploy", "stop"} and not args.execute:
            print("Dry run only. Repeat with --execute after reviewing the command and migration gate.")
            return 0
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except (ConfigError, ValueError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
