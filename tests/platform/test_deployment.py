from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import foxden


def configured(tmp_path: Path, mode: str) -> dict[str, str]:
    modules = foxden.MODES[mode]["modules"]
    values = {
        "FOXDEN_PUBLIC_ORIGIN": "http://127.0.0.1:18080",
        "FOXDEN_PUID": "10001",
        "FOXDEN_PGID": "10001",
        "FOXDEN_PORT": "18080",
        "FOXDEN_SECRETS_DIR": str(tmp_path / "secrets"),
        "FOXDEN_RUNTIME_DIR": str(tmp_path / "runtime"),
        "PORTAL_CONFIG_PATH": str(tmp_path / "portal"),
        "PORTAL_AUTH_MODE": "local",
        "PORTAL_MODULES_JSON": json.dumps([
            {"id": item, "name": item.title(), "base_url": f"http://{item}:8000", "navigation_path": f"/{item}/"}
            for item in sorted(modules)
        ]),
        "MUSICBRAINZ_CONTACT": "test@example.invalid",
        "QBIT_URL": "http://192.0.2.1:8080",
        "WIREGUARD_ADDRESSES": "10.2.0.2/32",
        "WIREGUARD_PUBLIC_KEY": "test-public-key",
        "WIREGUARD_ENDPOINT_IP": "192.0.2.2",
    }
    for key in (*foxden.MUSIC_PATHS, *foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS, "BROWSER_CONFIG_PATH"):
        values[key] = str(tmp_path / key.lower())
    for key in (*foxden.CORE_PATHS, *foxden.MUSIC_PATHS, *foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS):
        if key in values:
            Path(values[key]).mkdir(parents=True, exist_ok=True)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    secret_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        *foxden.SECRET_FILES,
        *foxden.MUSIC_SECRET_FILES,
        *foxden.MEDIA_SECRET_FILES,
        "wireguard-private-key",
        "oidc-client-secret",
    ):
        (secret_dir / name).write_text("x" * 40, encoding="utf-8")
    return values


@pytest.mark.parametrize("mode", sorted(foxden.MODES))
def test_each_mode_validates_independently(tmp_path: Path, mode: str) -> None:
    values = configured(tmp_path, mode)
    foxden.validate(mode, values)


def test_music_does_not_require_torrent_or_vpn_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    for key in (*foxden.MEDIA_PATHS, *foxden.MANAGED_PATHS, "QBIT_URL", "WIREGUARD_PUBLIC_KEY", "WIREGUARD_ENDPOINT_IP"):
        values.pop(key, None)
    foxden.validate("music", values)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for name in foxden.MEDIA_SECRET_FILES:
        (secret_dir / name).unlink()
    foxden.validate("music", values)


def test_media_does_not_require_music_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "media")
    for key in (*foxden.MUSIC_PATHS, "MUSICBRAINZ_CONTACT"):
        values.pop(key, None)
    foxden.validate("media", values)
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for name in foxden.MUSIC_SECRET_FILES:
        (secret_dir / name).unlink()
    foxden.validate("media", values)


def test_managed_mode_requires_vpn_configuration(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["WIREGUARD_PUBLIC_KEY"] = ""
    with pytest.raises(foxden.ConfigError, match="WIREGUARD_PUBLIC_KEY"):
        foxden.validate("full-managed", values)


def test_latest_image_tags_are_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "full-managed")
    values["QBIT_IMAGE"] = "lscr.io/linuxserver/qbittorrent:latest"
    with pytest.raises(foxden.ConfigError, match="pinned"):
        foxden.validate("full-managed", values)


def test_invalid_resource_limits_are_rejected(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    values["FOXDEN_APP_MEMORY_LIMIT"] = "unlimited"
    with pytest.raises(foxden.ConfigError, match="memory"):
        foxden.validate("music", values)


def test_compose_profiles_select_only_requested_modules(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    command = foxden.compose_command("full-managed", env, browser=True, action="config")
    assert command.count("--profile") == 4
    assert all(profile in command for profile in ("music", "media", "managed", "browser"))


def test_gateway_render_keeps_secret_out_of_return_value(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    secret = (Path(values["FOXDEN_SECRETS_DIR"]) / "ingress-auth").read_text(encoding="utf-8")
    target = foxden.render_gateway(values)
    assert target.name == "nginx.conf"
    assert secret in target.read_text(encoding="utf-8")
    assert secret not in str(target)


def test_initialization_generates_identity_and_does_not_overwrite_secrets(tmp_path: Path) -> None:
    values = configured(tmp_path, "music")
    secret_dir = Path(values["FOXDEN_SECRETS_DIR"])
    for item in secret_dir.iterdir():
        item.unlink()
    foxden.initialize(values, create_paths=False)
    original = (secret_dir / "portal-secret").read_text(encoding="utf-8")
    foxden.initialize(values, create_paths=False)
    assert (secret_dir / "portal-secret").read_text(encoding="utf-8") == original
    assert "BEGIN PRIVATE KEY" in (secret_dir / "identity-private.pem").read_text(encoding="utf-8")
    assert json.loads((secret_dir / "identity-public.json").read_text(encoding="utf-8"))["keys"][0]["kty"] == "OKP"


def test_managed_compose_forces_qbittorrent_through_gluetun() -> None:
    compose = (ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    qbit = compose.split("  qbittorrent:", 1)[1]
    assert "network_mode: service:gluetun" in qbit
    assert "gluetun: {condition: service_healthy}" in qbit
    assert "ports:" not in qbit.split("networks:", 1)[0]
    assert "FIREWALL: \"on\"" in compose
