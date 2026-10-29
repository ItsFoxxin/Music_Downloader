from __future__ import annotations

import base64
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from foxden_music.config import Settings
from foxden_music.web import create_app


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _keyset(path: Path, keys: dict[str, Ed25519PrivateKey]) -> None:
    from cryptography.hazmat.primitives import serialization

    path.write_text(json.dumps({"keys": [{
        "alg": "EdDSA", "crv": "Ed25519", "kid": kid, "kty": "OKP", "use": "sig",
        "x": _b64(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
    } for kid, key in keys.items()]}), encoding="utf-8")


def _assertion(key: Ed25519PrivateKey, *, kid: str = "portal-2026-10", audience: str = "music",
               roles: list[str] | None = None, scopes: list[str] | None = None,
               token_use: str = "user", now: int | None = None, lifetime: int = 45,
               algorithm: str = "EdDSA") -> str:
    issued = int(time.time()) if now is None else now
    header = {"alg": algorithm, "kid": kid, "typ": "foxden-identity+jwt"}
    payload = {
        "iss": "foxden-portal", "aud": audience, "sub": str(uuid.uuid4()),
        "preferred_username": "integration-user", "roles": roles if roles is not None else ["user"],
        "scope": scopes if scopes is not None else ["module:access"], "iat": issued,
        "nbf": issued - 2, "exp": issued + lifetime, "jti": uuid.uuid4().hex,
        "token_use": token_use,
    }
    unsigned = ".".join(_b64(json.dumps(item, sort_keys=True, separators=(",", ":")).encode())
                        for item in (header, payload))
    return f"{unsigned}.{_b64(key.sign(unsigned.encode('ascii')))}"


def _integrated(settings: Settings, tmp_path: Path, keys: dict[str, Ed25519PrivateKey]) -> Settings:
    trust = tmp_path / "portal-public.jwks.json"
    _keyset(trust, keys)
    return settings.model_copy(update={
        "foxden_identity_public_keys_file": trust,
        "foxden_public_origin": "https://media.example",
        "web_root_path": "/music",
    })


def _headers(token: str, *, origin: bool = False) -> dict[str, str]:
    values = {"X-FoxDen-Identity": token}
    if origin:
        values["Origin"] = "https://media.example"
    return values


def test_integrated_mode_protects_ui_but_preserves_public_health(settings, database, tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    app = create_app(_integrated(settings, tmp_path, {"portal-2026-10": key}), database)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/platform/v1/summary").status_code == 200
        assert client.get("/").status_code == 401
        assert client.get("/", headers={"X-FoxDen-Ingress": "1"}).status_code == 401
        page = client.get("/", headers=_headers(_assertion(key)))
        assert page.status_code == 200
        assert 'href="/music/add"' in page.text
        assert "/music/static/styles.css" in page.text
        assert client.get("/static/styles.css").status_code == 200
        assert client.get("/", headers=_headers(_assertion(key, audience="media"))).status_code == 401
        assert client.get("/", headers=_headers(_assertion(key, algorithm="HS256"))).status_code == 401


def test_signature_replay_expiry_and_rotation(settings, database, tmp_path) -> None:
    old, new = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    configured = _integrated(settings, tmp_path, {"old-key": old, "new-key": new})
    app = create_app(configured, database)
    replayed = _assertion(old, kid="old-key")
    with TestClient(app) as client:
        assert client.get("/", headers=_headers(replayed)).status_code == 200
        assert client.get("/", headers=_headers(replayed)).status_code == 401
        assert client.get("/", headers=_headers(_assertion(new, kid="new-key"))).status_code == 200
        assert client.get("/", headers=_headers(_assertion(new, kid="new-key", now=int(time.time()) - 90))).status_code == 401
        fresh = _assertion(new, kid="new-key")
        # Ed25519's 64-byte signature leaves unused base64 tail bits. Change
        # only those bits so a permissive decoder would produce identical
        # signature bytes while the JWT spelling itself is non-canonical.
        altered = fresh[:-1] + {"A": "B", "Q": "R", "g": "h", "w": "x"}[fresh[-1]]
        assert client.get("/", headers=_headers(altered)).status_code == 401

    # Restarting Music reloads the persistent public trust set; Portal can issue a fresh assertion.
    with TestClient(create_app(configured, database)) as restarted:
        assert restarted.get("/", headers=_headers(_assertion(new, kid="new-key"))).status_code == 200


def test_roles_origin_csrf_and_service_identity_are_separate(settings, database, tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    app = create_app(_integrated(settings, tmp_path, {"portal-2026-10": key}), database)
    with TestClient(app) as client:
        user_page = client.get("/library", headers=_headers(_assertion(key, roles=["user"])))
        assert user_page.status_code == 200
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', user_page.text).group(1)
        assert client.post("/library/scans", data={"csrf_token": csrf},
                           headers=_headers(_assertion(key, roles=["user"]), origin=True)).status_code == 403
        assert client.post("/library/scans", data={"csrf_token": csrf},
                           headers=_headers(_assertion(key, roles=["admin"]))).status_code == 403
        accepted = client.post("/library/scans", data={"csrf_token": csrf}, follow_redirects=False,
                               headers=_headers(_assertion(key, roles=["admin"]), origin=True))
        assert accepted.status_code == 303
        assert accepted.headers["location"].startswith("/music/library")

        service = _assertion(key, roles=[], scopes=["activity:read"], token_use="service")
        feed = client.get("/api/platform/v1/activity", headers=_headers(service))
        assert feed.status_code == 200 and feed.json()["module_id"] == "music"
        assert "/config" not in feed.text and "/staging" not in feed.text
        user = _assertion(key, roles=["admin"], scopes=["module:access"], token_use="user")
        assert client.get("/api/platform/v1/activity", headers=_headers(user)).status_code == 401


def test_concurrent_unique_assertions_are_accepted(settings, database, tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    app = create_app(_integrated(settings, tmp_path, {"portal-2026-10": key}), database)
    with TestClient(app) as client:
        def request_once(_: int) -> int:
            return client.get("/api/status", headers=_headers(_assertion(key))).status_code

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(request_once, range(24))) == [200] * 24


def test_standalone_mode_remains_unchanged(settings, database) -> None:
    with TestClient(create_app(settings, database)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").status_code == 200
