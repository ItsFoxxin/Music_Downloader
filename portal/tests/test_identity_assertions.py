from __future__ import annotations

import base64
import asyncio
import json
import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from foxden_identity import IdentityError, ReplayGuard, SigningKey, TrustedKeySet, generate_key_files
from foxden_portal.app import create_app
from foxden_portal.config import ModuleConfig
from foxden_portal.modules import ModuleClient
import httpx

from conftest import bootstrap_admin, settings


def keys(tmp_path, kid="foxden-test-1"):
    private, public = tmp_path / f"{kid}.pem", tmp_path / f"{kid}.json"
    generate_key_files(private, public, kid=kid)
    return SigningKey.from_file(private, kid=kid, issuer="foxden-portal"), TrustedKeySet.from_file(public), private, public


def user_token(signer, audience="media", now=1000, roles=None):
    return signer.issue(audience=audience, subject="user-1", username="fox",
                        roles=roles or ["user"], scopes=["module:access"],
                        token_use="user", now=now)


def test_valid_audience_roles_and_replay_protection(tmp_path):
    signer, trust, _private, _public = keys(tmp_path)
    token = user_token(signer, roles=["admin"])
    guard = ReplayGuard()
    claims = trust.verify(token, issuer="foxden-portal", audience="media", token_use="user",
                          required_scopes={"module:access"}, now=1010, replay_guard=guard)
    assert claims["sub"] == "user-1" and claims["roles"] == ["admin"]
    with pytest.raises(IdentityError, match="already been used"):
        trust.verify(token, issuer="foxden-portal", audience="media", token_use="user",
                     now=1010, replay_guard=guard)
    with pytest.raises(IdentityError):
        trust.verify(token, issuer="foxden-portal", audience="music", token_use="user", now=1010)
    with pytest.raises(IdentityError):
        trust.verify(token, issuer="untrusted-issuer", audience="media", token_use="user", now=1010)
    with pytest.raises(IdentityError):
        trust.verify(token, issuer="foxden-portal", audience="media", token_use="service", now=1010)


def test_rejects_altered_expired_malformed_and_unsupported_tokens(tmp_path):
    signer, trust, _private, _public = keys(tmp_path)
    token = user_token(signer)
    parts = token.split(".")
    altered = parts[0] + "." + parts[1] + "." + ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    noncanonical = token[:-1] + {"A": "B", "Q": "R", "g": "h", "w": "x"}[token[-1]]
    for bad in (altered, noncanonical, "not.a.token"):
        with pytest.raises(IdentityError):
            trust.verify(bad, issuer="foxden-portal", audience="media", token_use="user", now=1010)
    with pytest.raises(IdentityError, match="expired"):
        trust.verify(token, issuer="foxden-portal", audience="media", token_use="user", now=1060)
    future = user_token(signer, now=2000)
    with pytest.raises(IdentityError, match="allowed lifetime"):
        trust.verify(future, issuer="foxden-portal", audience="media", token_use="user", now=1900)
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    header["alg"] = "HS256"
    encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    with pytest.raises(IdentityError, match="unsupported"):
        trust.verify(encoded + "." + parts[1] + "." + parts[2], issuer="foxden-portal",
                     audience="media", token_use="user", now=1010)


def test_untrusted_key_and_rotation_window(tmp_path):
    old, _old_trust, _op, old_public = keys(tmp_path, "old")
    new, _new_trust, _np, new_public = keys(tmp_path, "new")
    combined = tmp_path / "combined.json"
    combined.write_text(json.dumps({"keys": json.loads(old_public.read_text())["keys"]
                                    + json.loads(new_public.read_text())["keys"]}), encoding="utf-8")
    rotating = TrustedKeySet.from_file(combined)
    assert rotating.verify(user_token(old), issuer="foxden-portal", audience="media", token_use="user", now=1010)
    assert rotating.verify(user_token(new), issuer="foxden-portal", audience="media", token_use="user", now=1010)
    new_only = TrustedKeySet.from_file(new_public)
    with pytest.raises(IdentityError, match="not trusted"):
        new_only.verify(user_token(old), issuer="foxden-portal", audience="media", token_use="user", now=1010)


def test_private_key_permissions_and_no_overwrite(tmp_path):
    _signer, _trust, private, public = keys(tmp_path)
    if os.name != "nt":
        assert private.stat().st_mode & 0o077 == 0
    with pytest.raises(IdentityError, match="overwrite"):
        generate_key_files(private, public, kid="portal-1")


def test_local_session_issues_audience_bound_assertion_and_revocation(tmp_path):
    signer, trust, private, _public = keys(tmp_path)
    configured = replace(settings(tmp_path), identity_private_key_path=private,
                         ingress_auth_secret="ingress-test-secret-123456789012345")
    with TestClient(create_app(configured)) as client:
        bootstrap_admin(client)
        ingress = {"X-FoxDen-Ingress": "1", "X-FoxDen-Ingress-Auth": configured.ingress_auth_secret}
        response = client.get("/api/platform/v1/session?audience=media", headers=ingress)
        token = response.headers["X-FoxDen-Identity"]
        claims = trust.verify(token, issuer="foxden-portal", audience="media", token_use="user",
                              required_scopes={"module:access"})
        assert response.status_code == 204 and claims["roles"] == ["admin"]
        assert client.get("/api/platform/v1/session?audience=music",
                          headers=ingress).status_code == 204
        csrf = client.cookies.get("foxden_portal_csrf")
        client.post("/logout", data={"csrf": csrf})
        assert client.get("/api/platform/v1/session?audience=media",
                          headers=ingress).status_code == 401
        assert token not in client.get("/health").text


def test_portal_uses_distinct_service_identity_for_sanitized_activity(tmp_path):
    signer, trust, _private, _public = keys(tmp_path)

    def handler(request: httpx.Request):
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json={
                "contract_version": "1.0", "module_id": "media", "module_name": "Movies & TV",
                "module_version": "test", "health": {"status": "healthy", "summary": "Ready"},
                "capabilities": [], "activity": [],
            })
        assertion = request.headers["X-FoxDen-Identity"]
        claims = trust.verify(assertion, issuer="foxden-portal", audience="media",
                              token_use="service", required_scopes={"activity:read"})
        assert claims["sub"] == "portal-activity" and claims["roles"] == []
        return httpx.Response(200, json={
            "contract_version": "1.0", "module_id": "media", "activity": [{
                "id": "safe-1", "kind": "media.request", "title": "Media request updated",
                "status": "complete", "occurred_at": "2026-10-27T12:00:00Z", "path": "/media/",
            }],
        })

    client = ModuleClient(.2, httpx.MockTransport(handler), service_assertion=lambda audience: signer.issue(
        audience=audience, subject="portal-activity", username="portal-activity", roles=[],
        scopes=["activity:read"], token_use="service"))
    snapshot = asyncio.run(client.fetch(ModuleConfig("media", "Movies & TV", "http://media.test", "/media/")))
    assert snapshot.state == "healthy" and snapshot.activity[0]["title"] == "Media request updated"


def test_invalid_private_activity_cannot_poison_module_health(tmp_path):
    signer, _trust, _private, _public = keys(tmp_path)

    def handler(request: httpx.Request):
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json={
                "contract_version": "1.0", "module_id": "media", "module_name": "Movies & TV",
                "module_version": "test", "health": {"status": "healthy", "summary": "Ready"},
                "capabilities": [], "activity": [{"id": "public", "kind": "leak",
                    "title": "must not display", "status": "complete",
                    "occurred_at": "2026-10-27T12:00:00Z", "path": "/"}],
            })
        return httpx.Response(200, json={"private_path": "/mnt/private", "token": "secret"})

    client = ModuleClient(.2, httpx.MockTransport(handler), service_assertion=lambda audience: signer.issue(
        audience=audience, subject="portal-activity", username="portal-activity", roles=[],
        scopes=["activity:read"], token_use="service"))
    snapshot = asyncio.run(client.fetch(ModuleConfig("media", "Movies & TV", "http://media.test", "/media/")))
    assert snapshot.state == "healthy" and snapshot.activity == ()
