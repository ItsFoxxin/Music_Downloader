import asyncio
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

from authlib.jose import JsonWebKey, JsonWebToken
import httpx

from foxden_portal.database import PortalStore
from foxden_portal.oidc import OIDCClient, OIDCError

from conftest import settings


def protocol_fixture(tmp_path, token_factory=None):
    configured = settings(tmp_path, auth_mode="hybrid")
    store = PortalStore(configured.database_path)
    store.initialize()
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "portal-test"})
    public = key.as_dict(is_private=False)
    issuer = configured.oidc_issuer
    document = {
        "issuer": issuer,
        "authorization_endpoint": "https://auth.example/authorize",
        "token_endpoint": "https://auth.example/token",
        "jwks_uri": "https://auth.example/jwks",
        "end_session_endpoint": "https://auth.example/logout",
        "code_challenge_methods_supported": ["S256"],
    }
    token_holder = {"value": None}

    def handler(request: httpx.Request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=document)
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [public]})
        if request.url.path == "/token":
            return httpx.Response(200, json={"id_token": token_holder["value"]})
        raise AssertionError(f"unexpected request {request.url}")

    client = OIDCClient(configured, store, httpx.MockTransport(handler))
    return configured, store, key, document, token_holder, client


def sign(key, configured, nonce, **overrides):
    now = int(time.time())
    claims = {"iss": configured.oidc_issuer, "aud": configured.oidc_client_id,
              "sub": "stable-subject", "iat": now, "exp": now + 300, "nonce": nonce,
              "preferred_username": "fox", "groups": ["foxden-admins"]}
    claims.update(overrides)
    return JsonWebToken(["RS256"]).encode({"alg": "RS256", "kid": "portal-test"}, claims, key).decode()


def test_authorization_request_uses_state_nonce_and_pkce_s256(tmp_path):
    configured, store, _key, _document, _holder, client = protocol_fixture(tmp_path)
    target = asyncio.run(client.begin())
    query = parse_qs(urlsplit(target).query)
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid profile email"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["state"][0]) >= 32 and len(query["nonce"][0]) >= 32
    with store.connection() as db:
        row = db.execute("SELECT * FROM oidc_flows").fetchone()
        expected = base64.urlsafe_b64encode(hashlib.sha256(row["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        assert query["code_challenge"] == [expected]


def test_verified_token_completes_once_and_replay_fails(tmp_path):
    configured, store, key, _document, holder, client = protocol_fixture(tmp_path)
    target = asyncio.run(client.begin())
    state = parse_qs(urlsplit(target).query)["state"][0]
    with store.connection() as db:
        nonce = db.execute("SELECT nonce FROM oidc_flows").fetchone()[0]
    holder["value"] = sign(key, configured, nonce)
    claims, _flow = asyncio.run(client.finish(state, "authorization-code"))
    assert claims["sub"] == "stable-subject"
    try:
        asyncio.run(client.finish(state, "authorization-code"))
    except OIDCError as exc:
        assert "state" in str(exc)
    else:
        raise AssertionError("OIDC state replay was accepted")


def test_wrong_signature_expired_token_and_nonce_are_rejected(tmp_path):
    configured, _store, key, document, _holder, client = protocol_fixture(tmp_path)
    other = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "portal-test"})
    wrong = sign(other, configured, "nonce")
    # The verifier intentionally allows 30 seconds of clock skew.
    expired = sign(key, configured, "nonce", exp=int(time.time()) - 60)
    valid_wrong_nonce = sign(key, configured, "other")
    for token, nonce in ((wrong, "nonce"), (expired, "nonce"), (valid_wrong_nonce, "nonce")):
        try:
            asyncio.run(client.validate_id_token(token, document, nonce))
        except OIDCError:
            pass
        else:
            raise AssertionError("Invalid ID token was accepted")
