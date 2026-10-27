from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from foxden_portal.app import create_app
from foxden_portal.config import ModuleConfig, Settings
from foxden_portal.modules import ModuleClient


BOOTSTRAP = "bootstrap-secret-for-tests-only-123456789"
PORTAL_SECRET = "portal-secret-for-tests-only-123456789012"
PASSWORD = "Correct-Horse-Battery-7!"


def settings(tmp_path: Path, modules: tuple[ModuleConfig, ...] = (), auth_mode: str = "local") -> Settings:
    return Settings(
        database_path=tmp_path / "portal.db", public_url="http://testserver",
        secret_key=PORTAL_SECRET, bootstrap_secret=BOOTSTRAP, bootstrap_expires_seconds=3600,
        auth_mode=auth_mode, cookie_secure=False, session_seconds=3600,
        login_max_attempts=3, login_window_seconds=900, login_lock_seconds=900,
        module_timeout_seconds=.2, modules=modules,
        oidc_issuer="https://auth.example/application/o/fox-den-media" if auth_mode in {"oidc", "hybrid"} else None,
        oidc_client_id="portal-client" if auth_mode in {"oidc", "hybrid"} else None,
        oidc_client_secret="test-client-secret-123456" if auth_mode in {"oidc", "hybrid"} else None,
        oidc_redirect_uri="http://testserver/auth/oidc/callback" if auth_mode in {"oidc", "hybrid"} else None,
        oidc_scopes=("openid", "profile", "email"), oidc_allowed_groups=(), oidc_admin_groups=("foxden-admins",),
        oidc_logout="local", identity_private_key_path=None,
        identity_signing_kid="foxden-test-1", identity_issuer="foxden-portal",
        identity_lifetime_seconds=45,
    )


def csrf(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match
    return match.group(1)


def bootstrap_admin(client: TestClient, username: str = "admin") -> None:
    page = client.get("/setup")
    assert page.status_code == 200
    response = client.post("/setup", data={
        "csrf": csrf(page.text), "bootstrap_secret": BOOTSTRAP, "username": username,
        "display_name": "Fox Admin", "password": PASSWORD,
    }, follow_redirects=False)
    assert response.status_code == 303


def login(client: TestClient, username: str = "admin", password: str = PASSWORD):
    page = client.get("/login")
    return client.post("/login", data={"csrf": csrf(page.text), "username": username, "password": password},
                       follow_redirects=False)


@pytest.fixture
def local_client(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        yield client


def module_transport(responses: dict[str, object]) -> httpx.MockTransport:
    counts: dict[str, int] = {}

    def handler(request: httpx.Request):
        host = request.url.host
        value = responses[host]
        if isinstance(value, list):
            index = counts.get(host, 0)
            counts[host] = index + 1
            value = value[min(index, len(value) - 1)]
        if isinstance(value, Exception):
            raise value
        return httpx.Response(200, json=value)

    return httpx.MockTransport(handler)


def module_summary(module_id: str, health: str = "healthy") -> dict:
    return {
        "contract_version": "1.0", "module_id": module_id,
        "module_name": "Music" if module_id == "music" else "Movies & TV",
        "module_version": "test-1.0", "health": {"status": health, "summary": f"{module_id} {health}"},
        "capabilities": [{"id": "library", "label": "Library", "enabled": True}],
        "activity": [{"id": f"{module_id}-1", "kind": "import", "title": f"{module_id} item",
                      "status": "complete", "occurred_at": "2026-10-26T12:00:00Z", "path": "/history"}],
    }
