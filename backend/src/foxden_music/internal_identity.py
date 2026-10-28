"""Strict verification for Portal-issued Fox Den Ed25519 assertions.

This module intentionally contains verification only. Music never receives a
Portal private key and cannot mint user or service identities.
"""
from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
import re
import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ALGORITHM = "EdDSA"
TOKEN_TYPE = "foxden-identity+jwt"
CLAIMS = {
    "iss", "aud", "sub", "preferred_username", "roles", "scope",
    "iat", "nbf", "exp", "jti", "token_use",
}
SAFE_VALUE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@:._-]{0,99}$")


class IdentityError(ValueError):
    """A deliberately non-sensitive internal identity failure."""


def _decode(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IdentityError("Internal identity assertion is invalid.") from exc


def _document(value: str) -> dict:
    try:
        parsed = json.loads(_decode(value).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityError("Internal identity assertion is invalid.") from exc
    if not isinstance(parsed, dict):
        raise IdentityError("Internal identity assertion is invalid.")
    return parsed


class ReplayGuard:
    """Thread-safe bounded replay cache for short-lived assertion IDs."""

    def __init__(self, maximum: int = 10_000):
        self.maximum = maximum
        self._seen: dict[str, int] = {}
        self._lock = threading.Lock()

    def check_and_mark(self, token_id: str, expires: int, now: int) -> None:
        with self._lock:
            self._seen = {key: value for key, value in self._seen.items() if value > now}
            if token_id in self._seen:
                raise IdentityError("Internal identity assertion was already used.")
            if len(self._seen) >= self.maximum:
                raise IdentityError("Internal identity replay protection is unavailable.")
            self._seen[token_id] = expires


class TrustedKeySet:
    def __init__(self, keys: dict[str, Ed25519PublicKey]):
        if not keys:
            raise IdentityError("Internal identity trust set is empty.")
        self.keys = keys

    @classmethod
    def from_file(cls, path: Path) -> "TrustedKeySet":
        if path.is_symlink():
            raise IdentityError("Internal identity trust file must not be a symlink.")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            entries = document["keys"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise IdentityError("Internal identity trust file is unreadable or invalid.") from exc
        if not isinstance(entries, list) or not 1 <= len(entries) <= 20:
            raise IdentityError("Internal identity trust set is invalid.")
        keys: dict[str, Ed25519PublicKey] = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"alg", "crv", "kid", "kty", "use", "x"}:
                raise IdentityError("Internal identity public key is malformed.")
            if (entry["alg"], entry["crv"], entry["kty"], entry["use"]) != (
                ALGORITHM, "Ed25519", "OKP", "sig",
            ):
                raise IdentityError("Internal identity public key algorithm is unsupported.")
            kid = entry["kid"]
            if not isinstance(kid, str) or not SAFE_VALUE.fullmatch(kid) or kid in keys:
                raise IdentityError("Internal identity key ID is invalid or duplicated.")
            try:
                raw = _decode(entry["x"])
                if len(raw) != 32:
                    raise ValueError
                keys[kid] = Ed25519PublicKey.from_public_bytes(raw)
            except ValueError as exc:
                raise IdentityError("Internal identity public key is invalid.") from exc
        return cls(keys)

    def verify(
        self,
        token: str,
        *,
        issuer: str,
        audience: str,
        token_use: str,
        required_scopes: set[str],
        allowed_roles: set[str] | None = None,
        now: int | None = None,
        replay_guard: ReplayGuard | None = None,
    ) -> dict:
        if not isinstance(token, str) or len(token) > 8192:
            raise IdentityError("Internal identity assertion is invalid.")
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
        except ValueError as exc:
            raise IdentityError("Internal identity assertion is invalid.") from exc
        header, payload = _document(encoded_header), _document(encoded_payload)
        if set(header) != {"alg", "kid", "typ"} or header.get("alg") != ALGORITHM or header.get("typ") != TOKEN_TYPE:
            raise IdentityError("Internal identity assertion algorithm is unsupported.")
        key = self.keys.get(header.get("kid"))
        if key is None:
            raise IdentityError("Internal identity signing key is not trusted.")
        try:
            key.verify(_decode(encoded_signature), f"{encoded_header}.{encoded_payload}".encode("ascii"))
        except (InvalidSignature, ValueError, UnicodeEncodeError) as exc:
            raise IdentityError("Internal identity assertion signature is invalid.") from exc
        if set(payload) != CLAIMS:
            raise IdentityError("Internal identity claims are malformed.")
        if payload.get("iss") != issuer or payload.get("aud") != audience or payload.get("token_use") != token_use:
            raise IdentityError("Internal identity issuer, audience, or use is invalid.")
        for field in ("sub", "preferred_username", "jti"):
            if not isinstance(payload.get(field), str) or not SAFE_VALUE.fullmatch(payload[field]):
                raise IdentityError("Internal identity claim is invalid.")
        for field in ("roles", "scope"):
            values = payload.get(field)
            if not isinstance(values, list) or len(values) > 20 or len(values) != len(set(values)):
                raise IdentityError("Internal identity roles or scopes are invalid.")
            if any(not isinstance(value, str) or not SAFE_VALUE.fullmatch(value) for value in values):
                raise IdentityError("Internal identity roles or scopes are invalid.")
        if not all(isinstance(payload.get(field), int) and not isinstance(payload[field], bool)
                   for field in ("iat", "nbf", "exp")):
            raise IdentityError("Internal identity times are invalid.")
        current = int(time.time()) if now is None else now
        lifetime = payload["exp"] - payload["iat"]
        if not 30 <= lifetime <= 60 or payload["nbf"] > current + 5 or payload["iat"] > current + 5 or payload["exp"] <= current:
            raise IdentityError("Internal identity assertion is expired or outside its allowed lifetime.")
        if not required_scopes.issubset(payload["scope"]):
            raise IdentityError("Internal identity assertion lacks a required scope.")
        if allowed_roles is not None and (not payload["roles"] or not set(payload["roles"]).issubset(allowed_roles)):
            raise IdentityError("Internal identity role is invalid.")
        if replay_guard:
            replay_guard.check_and_mark(payload["jti"], payload["exp"], current)
        return payload
