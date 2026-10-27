import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from foxden_portal.app import create_app
from foxden_portal.config import ConfigError, Settings
from foxden_portal.contracts import (
    CONTRACT_VERSION,
    IdentityError,
    ModuleSummary,
    issue_identity_assertion,
    verify_identity_assertion,
)

from conftest import ASSERTION_SECRET, bootstrap_admin, settings


def test_checked_in_module_schema_matches_runtime_contract():
    schema_path = Path(__file__).parents[2] / "contracts" / "v1" / "module-summary.schema.json"
    checked_in = json.loads(schema_path.read_text(encoding="utf-8"))
    runtime = ModuleSummary.model_json_schema()
    assert checked_in["properties"]["contract_version"]["const"] == CONTRACT_VERSION
    assert set(checked_in["required"]) == set(runtime["required"])
    assert checked_in["properties"]["capabilities"]["maxItems"] == 50
    assert checked_in["properties"]["activity"]["maxItems"] == 20


def test_internal_identity_round_trip_and_rejects_spoofing(tmp_path):
    token = issue_identity_assertion(secret=ASSERTION_SECRET, issuer="foxden-portal", audience="music",
                                     subject="user-id", username="fox", roles=["admin"], now=1000)
    claims = verify_identity_assertion(token, secret=ASSERTION_SECRET, issuer="foxden-portal",
                                       audience="music", now=1020)
    assert claims["sub"] == "user-id" and claims["roles"] == ["admin"]
    with pytest.raises(IdentityError):
        verify_identity_assertion(token, secret="untrusted-secret-which-is-long-enough", issuer="foxden-portal",
                                  audience="music", now=1020)
    with pytest.raises(IdentityError):
        verify_identity_assertion(token, secret=ASSERTION_SECRET, issuer="foxden-portal",
                                  audience="media", now=1020)
    with pytest.raises(IdentityError):
        verify_identity_assertion(token, secret=ASSERTION_SECRET, issuer="foxden-portal",
                                  audience="music", now=2000)
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.get("/health", headers={"X-FoxDen-Identity": token}).status_code == 400


def test_config_validation_and_redaction(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_INTERNAL_ASSERTION_SECRET", "assertion-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_COOKIE_SECURE", "false")
    monkeypatch.setenv("PORTAL_MODULES_JSON", json.dumps([{
        "id": "music", "name": "Music", "base_url": "http://music:8000", "navigation_path": "/music/"
    }]))
    configured = Settings.from_env()
    redacted = configured.redacted()
    assert redacted["bootstrap_configured"] is True
    assert "secret" not in json.dumps(redacted).lower()
    assert configured.modules[0].module_id == "music"


def test_config_rejects_credentials_in_module_url(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_INTERNAL_ASSERTION_SECRET", "assertion-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_MODULES_JSON", '[{"id":"music","name":"Music","base_url":"http://user:pass@music:8000","navigation_path":"/music/"}]')
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_local_mode_requires_no_oidc(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "portal.db"))
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-configuration-secret-123456789")
    monkeypatch.setenv("PORTAL_INTERNAL_ASSERTION_SECRET", "assertion-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_BOOTSTRAP_SECRET", "bootstrap-configuration-secret-123456")
    monkeypatch.setenv("PORTAL_AUTH_MODE", "local")
    configured = Settings.from_env()
    assert configured.local_enabled and not configured.oidc_enabled


def test_responsive_navigation_and_state_styles_exist(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        page = client.get("/")
        css = client.get("/static/portal.css")
        assert 'name="viewport"' in page.text
        assert 'aria-label="Platform"' in page.text
        assert "@media(max-width:680px)" in css.text
        for state in ("healthy", "unhealthy", "offline"):
            assert f"state-{state}" in css.text
