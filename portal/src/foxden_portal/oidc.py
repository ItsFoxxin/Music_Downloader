from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit

from authlib.jose import JsonWebToken, JoseError
import httpx

from .config import Settings
from .database import PortalStore


class OIDCError(ValueError):
    pass


class OIDCUnavailable(OIDCError):
    pass


class OIDCClient:
    ALGORITHMS = ["RS256", "ES256"]

    def __init__(self, settings: Settings, store: PortalStore, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.store = store
        self.transport = transport
        self._discovery: tuple[float, dict] | None = None

    async def discovery(self) -> dict:
        if self._discovery and self._discovery[0] > time.monotonic():
            return self._discovery[1]
        issuer = self.settings.oidc_issuer
        if not issuer:
            raise OIDCError("OIDC is disabled.")
        url = issuer + "/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5), transport=self.transport,
                                         follow_redirects=False) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
                if len(response.content) > 128 * 1024:
                    raise OIDCError("OIDC discovery response is too large.")
                document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OIDCUnavailable("The identity provider is unavailable.") from exc
        required = {"issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"}
        if not required.issubset(document) or document["issuer"].rstrip("/") != issuer:
            raise OIDCError("OIDC discovery metadata is invalid.")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            parsed = urlsplit(document[key])
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise OIDCError("OIDC discovery contains an unsafe endpoint.")
        supported = set(document.get("code_challenge_methods_supported", ["S256"]))
        if "S256" not in supported:
            raise OIDCError("The identity provider does not advertise PKCE S256.")
        self._discovery = (time.monotonic() + 300, document)
        return document

    async def begin(self, return_to: str = "/") -> str:
        document = await self.discovery()
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.store.create_oidc_flow(state, nonce, verifier, return_to)
        query = urlencode({
            "response_type": "code", "client_id": self.settings.oidc_client_id,
            "redirect_uri": self.settings.oidc_redirect_uri,
            "scope": " ".join(self.settings.oidc_scopes), "state": state, "nonce": nonce,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return document["authorization_endpoint"] + "?" + query

    async def finish(self, state: str, code: str) -> tuple[dict, dict]:
        flow = self.store.consume_oidc_flow(state)
        if not flow:
            raise OIDCError("OIDC state is invalid, expired, or already used.")
        document = await self.discovery()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8), transport=self.transport,
                                         follow_redirects=False) as client:
                response = await client.post(document["token_endpoint"], data={
                    "grant_type": "authorization_code", "code": code,
                    "redirect_uri": self.settings.oidc_redirect_uri,
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                    "code_verifier": flow["code_verifier"],
                }, headers={"Accept": "application/json"})
                response.raise_for_status()
                tokens = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OIDCUnavailable("The identity provider could not complete login.") from exc
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str):
            raise OIDCError("The identity provider did not return an ID token.")
        claims = await self.validate_id_token(id_token, document, flow["nonce"])
        return claims, flow

    async def validate_id_token(self, token: str, document: dict, nonce: str) -> dict:
        try:
            header_segment = token.split(".", 1)[0]
            header = json.loads(base64.urlsafe_b64decode(header_segment + "=" * (-len(header_segment) % 4)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise OIDCError("ID token is malformed.") from exc
        if header.get("alg") not in self.ALGORITHMS:
            raise OIDCError("ID token uses an unsupported signature algorithm.")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5), transport=self.transport,
                                         follow_redirects=False) as client:
                response = await client.get(document["jwks_uri"], headers={"Accept": "application/json"})
                response.raise_for_status()
                jwks = response.json()
            claims = JsonWebToken(self.ALGORITHMS).decode(token, jwks, claims_options={
                "iss": {"essential": True, "value": self.settings.oidc_issuer},
                "aud": {"essential": True, "value": self.settings.oidc_client_id},
                "exp": {"essential": True}, "iat": {"essential": True}, "sub": {"essential": True},
            })
            claims.validate(leeway=30)
        except (httpx.HTTPError, ValueError, JoseError) as exc:
            raise OIDCError("ID token validation failed.") from exc
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OIDCError("ID token nonce validation failed.")
        return dict(claims)

    def authorize_claims(self, claims: dict) -> tuple[str, str, str, list[str], str]:
        subject = str(claims.get("sub", ""))
        if not subject or len(subject) > 255:
            raise OIDCError("OIDC subject is missing or invalid.")
        raw_groups = claims.get("groups", [])
        groups = [str(group) for group in raw_groups] if isinstance(raw_groups, list) else []
        allowed = set(self.settings.oidc_allowed_groups)
        if allowed and not allowed.intersection(groups):
            raise OIDCError("This identity is not authorized for Fox Den Media.")
        role = "admin" if set(self.settings.oidc_admin_groups).intersection(groups) else "user"
        username = str(claims.get("preferred_username") or claims.get("email") or "oidc-user").split("@")[0]
        username = "".join(ch for ch in username.lower() if ch.isalnum() or ch in "._-")[:32] or "oidc-user"
        if len(username) < 3:
            username = "oidc-user"
        display_name = str(claims.get("name") or claims.get("preferred_username") or username)[:100]
        return subject, username, display_name, groups, role
