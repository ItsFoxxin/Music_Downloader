from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from foxden_identity import SigningKey, generate_key_files
from app.config import Settings
from app.main import create_app


def identity_files(tmp_path):
    private, public = tmp_path / "identity.pem", tmp_path / "identity.json"
    generate_key_files(private, public, kid="test-1")
    return SigningKey.from_file(private, kid="test-1", issuer="foxden-portal"), public


def token(signer, *, audience="media", token_use="user", roles=None, scopes=None):
    return signer.issue(audience=audience, subject="subject-1", username="fox",
                        roles=["user"] if roles is None else roles,
                        scopes=["module:access"] if scopes is None else scopes,
                        token_use=token_use)


def configured_settings(tmp_path):
    configured = Settings(
        config=tmp_path / "config", staging=tmp_path / "staging", media=tmp_path / "media",
        token="test-token-with-at-least-24-characters", settle_seconds=0,
    )
    configured.prepare()
    return configured


def test_module_accepts_correct_user_and_rejects_cross_module_replay_and_forgery(tmp_path, caplog):
    signer, public = identity_files(tmp_path)
    configured = replace(configured_settings(tmp_path), identity_public_keys_file=public,
                         public_origin="https://media.example")
    with TestClient(create_app(configured, start_worker=False)) as client:
        assertion = token(signer, roles=["admin"])
        response = client.get("/api/status", headers={"X-FoxDen-Identity": assertion})
        assert response.status_code == 200
        restricted_session = client.post("/api/session", headers={
            "X-FoxDen-Identity": token(signer), "Origin": "https://media.example",
        })
        assert restricted_session.status_code == 200
        assert "foxden_session" not in restricted_session.headers.get("set-cookie", "")
        restricted = token(signer)
        denied = client.post("/api/requests", headers={"X-FoxDen-Identity": restricted},
                             json={"query": "Example", "media_type": "Movie"})
        assert denied.status_code == 403
        administrator = token(signer, roles=["admin"])
        assert client.post("/api/requests", headers={"X-FoxDen-Identity": administrator,
                                                     "Origin": "https://media.example"},
                           json={"query": "Example", "media_type": "Movie"}).status_code == 202
        no_origin = token(signer, roles=["admin"])
        assert client.post("/api/requests", headers={"X-FoxDen-Identity": no_origin},
                           json={"query": "Example", "media_type": "Movie"}).status_code == 403
        assert client.get("/api/status", headers={"X-FoxDen-Identity": assertion}).status_code == 401
        assert client.get("/api/status", headers={"X-FoxDen-Identity": token(signer, audience="music")}).status_code == 401
        forged = token(signer)
        parts = forged.split(".")
        parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
        forged = ".".join(parts)
        failure = client.get("/api/status", headers={"X-FoxDen-Identity": forged})
        assert failure.status_code == 401 and failure.json() == {"detail": "Authentication required."}
        assert assertion not in failure.text and forged not in failure.text
        assert assertion not in caplog.text and forged not in caplog.text


def test_service_activity_is_separate_scoped_and_sanitized(tmp_path):
    signer, public = identity_files(tmp_path)
    configured = replace(configured_settings(tmp_path), identity_public_keys_file=public,
                         public_origin="https://media.example")
    with TestClient(create_app(configured, start_worker=False)) as client:
        client.app.state.store.create_request("Movie", "https://private.example/secret-token", "Private title")
        service = token(signer, token_use="service", roles=[], scopes=["activity:read"])
        response = client.get("/api/platform/v1/activity", headers={"X-FoxDen-Identity": service})
        assert response.status_code == 200
        body = response.json()
        assert body["module_id"] == "media" and body["activity"][0]["title"] == "Media request updated"
        rendered = response.text
        assert "Private title" not in rendered and "secret-token" not in rendered
        user = token(signer)
        assert client.get("/api/platform/v1/activity", headers={"X-FoxDen-Identity": user}).status_code == 401
        service_for_status = token(signer, token_use="service", roles=[], scopes=["activity:read"])
        assert client.get("/api/status", headers={"X-FoxDen-Identity": service_for_status}).status_code == 401


def test_legacy_module_auth_remains_compatible_without_identity_keys(tmp_path):
    configured = configured_settings(tmp_path)
    with TestClient(create_app(configured, start_worker=False)) as client:
        response = client.get("/api/status", headers={"Authorization": f"Bearer {configured.token}"})
        assert response.status_code == 200
