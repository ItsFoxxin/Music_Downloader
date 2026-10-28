from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
COMPOSE_PATH = ROOT / "integration" / "compose.yaml"
COMPOSE_TEXT = COMPOSE_PATH.read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXT)


def test_integration_stack_contains_only_approved_services_and_loopback_ingress():
    services = COMPOSE["services"]
    assert set(services) == {"volume-init", "ingress", "portal", "music", "music-worker", "media"}
    assert services["ingress"]["ports"] == ["127.0.0.1:${INTEGRATION_PORT:-18080}:8080"]
    assert all("ports" not in value for name, value in services.items() if name != "ingress")
    assert COMPOSE["networks"]["platform"]["internal"] is True
    assert services["volume-init"]["network_mode"] == "none"


def test_integration_storage_is_disposable_and_has_no_production_mounts():
    assert set(COMPOSE["volumes"]) == {
        "portal-config", "music-config", "music-staging", "music-library", "music-downloads",
        "media-config", "media-staging", "media-library",
    }
    forbidden = ("/mnt/", "@usb", "qbittorrent", "gluetun", "proton", "docker.sock")
    lowered = COMPOSE_TEXT.lower()
    assert not any(value.lower() in lowered for value in forbidden)
    assert "${MUSIC_SOURCE_PATH:?" in COMPOSE_TEXT
    assert "./music/backend" not in COMPOSE_TEXT


def test_application_containers_are_non_root_read_only_and_identity_is_asymmetric():
    for name in ("portal", "music", "music-worker", "media"):
        service = COMPOSE["services"][name]
        assert service.get("user", COMPOSE["x-music-service"].get("user")) == "10001:10001"
        assert service.get("read_only", COMPOSE["x-music-service"].get("read_only")) is True
    portal_mounts = "\n".join(COMPOSE["services"]["portal"]["volumes"])
    assert "private.pem" in portal_mounts
    for name in ("music", "music-worker", "media"):
        mounts = "\n".join(COMPOSE["services"][name].get("volumes", COMPOSE["x-music-service"]["volumes"]))
        assert "public.json" in mounts and "private.pem" not in mounts


def test_generated_runtime_state_is_ignored_and_production_compose_is_not_overridden():
    assert "integration/.runtime/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert COMPOSE_PATH.name == "compose.yaml"
    assert COMPOSE_PATH.parent.name == "integration"
    assert "integration/compose.yaml" not in (ROOT / "compose.yaml").read_text(encoding="utf-8")
