"""Strict Ed25519 identity assertions shared by Portal and Fox Den modules."""
from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


ALGORITHM = "EdDSA"
TOKEN_TYPE = "foxden-identity+jwt"
CLAIMS = {"iss", "aud", "sub", "preferred_username", "roles", "scope",
          "iat", "nbf", "exp", "jti", "token_use"}
SAFE_VALUE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@:._-]{0,99}$")


class IdentityError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IdentityError("Identity assertion is malformed.") from exc


def _json(value: str) -> dict:
    try:
        parsed = json.loads(_unb64(value).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityError("Identity assertion is malformed.") from exc
    if not isinstance(parsed, dict):
        raise IdentityError("Identity assertion is malformed.")
    return parsed


class ReplayGuard:
    def __init__(self, maximum: int = 10000):
        self.maximum = maximum
        self._seen: dict[str, int] = {}
        self._lock = threading.Lock()

    def check_and_mark(self, token_id: str, expires: int, now: int) -> None:
        with self._lock:
            self._seen = {key: value for key, value in self._seen.items() if value > now}
            if token_id in self._seen:
                raise IdentityError("Identity assertion has already been used.")
            if len(self._seen) >= self.maximum:
                raise IdentityError("Identity replay cache is full.")
            self._seen[token_id] = expires


class SigningKey:
    def __init__(self, key: Ed25519PrivateKey, *, kid: str, issuer: str, lifetime: int = 45):
        if not SAFE_VALUE.fullmatch(kid) or not SAFE_VALUE.fullmatch(issuer):
            raise IdentityError("Identity key ID or issuer is invalid.")
        if not 30 <= lifetime <= 60:
            raise IdentityError("Identity assertion lifetime must be 30 to 60 seconds.")
        self.key, self.kid, self.issuer, self.lifetime = key, kid, issuer, lifetime

    @classmethod
    def from_file(cls, path: Path, *, kid: str, issuer: str, lifetime: int = 45) -> "SigningKey":
        if path.is_symlink():
            raise IdentityError("Identity private key file must not be a symlink.")
        try:
            if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise IdentityError("Identity private key file permissions must not allow group or other access.")
            loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
        except IdentityError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise IdentityError("Identity private key file is unreadable or invalid.") from exc
        if not isinstance(loaded, Ed25519PrivateKey):
            raise IdentityError("Identity private key must be Ed25519.")
        return cls(loaded, kid=kid, issuer=issuer, lifetime=lifetime)

    def issue(self, *, audience: str, subject: str, username: str, roles: list[str],
              scopes: list[str], token_use: str, now: int | None = None) -> str:
        if token_use not in {"user", "service"}:
            raise IdentityError("Identity token use is invalid.")
        values = [audience, subject, username, *roles, *scopes]
        if any(not isinstance(value, str) or not SAFE_VALUE.fullmatch(value) for value in values):
            raise IdentityError("Identity assertion contains an invalid value.")
        issued = int(time.time()) if now is None else now
        header = {"alg": ALGORITHM, "kid": self.kid, "typ": TOKEN_TYPE}
        payload = {
            "iss": self.issuer, "aud": audience, "sub": subject,
            "preferred_username": username, "roles": sorted(set(roles)),
            "scope": sorted(set(scopes)), "iat": issued, "nbf": issued - 2,
            "exp": issued + self.lifetime, "jti": secrets.token_hex(18),
            "token_use": token_use,
        }
        encoded = ".".join((_b64(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
                            _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())))
        return encoded + "." + _b64(self.key.sign(encoded.encode("ascii")))


class TrustedKeySet:
    def __init__(self, keys: dict[str, Ed25519PublicKey]):
        if not keys:
            raise IdentityError("Identity public-key trust set is empty.")
        self.keys = keys

    @classmethod
    def from_file(cls, path: Path) -> "TrustedKeySet":
        if path.is_symlink():
            raise IdentityError("Identity public-key file must not be a symlink.")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            entries = document["keys"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise IdentityError("Identity public-key file is unreadable or invalid.") from exc
        if not isinstance(entries, list) or not 1 <= len(entries) <= 20:
            raise IdentityError("Identity public-key trust set is invalid.")
        keys: dict[str, Ed25519PublicKey] = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"alg", "crv", "kid", "kty", "use", "x"}:
                raise IdentityError("Identity public key is malformed.")
            if entry["alg"] != ALGORITHM or entry["crv"] != "Ed25519" or entry["kty"] != "OKP" or entry["use"] != "sig":
                raise IdentityError("Identity public key uses an unsupported algorithm.")
            kid = entry["kid"]
            if not isinstance(kid, str) or not SAFE_VALUE.fullmatch(kid) or kid in keys:
                raise IdentityError("Identity public key ID is invalid or duplicated.")
            try:
                keys[kid] = Ed25519PublicKey.from_public_bytes(_unb64(entry["x"]))
            except ValueError as exc:
                raise IdentityError("Identity public key is invalid.") from exc
        return cls(keys)

    def verify(self, token: str, *, issuer: str, audience: str, token_use: str,
               required_scopes: set[str] | None = None, now: int | None = None,
               replay_guard: ReplayGuard | None = None) -> dict:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
        except ValueError as exc:
            raise IdentityError("Identity assertion is malformed.") from exc
        header, payload = _json(encoded_header), _json(encoded_payload)
        if set(header) != {"alg", "kid", "typ"} or header.get("alg") != ALGORITHM or header.get("typ") != TOKEN_TYPE:
            raise IdentityError("Identity assertion algorithm or type is unsupported.")
        key = self.keys.get(header.get("kid"))
        if key is None:
            raise IdentityError("Identity assertion signing key is not trusted.")
        try:
            key.verify(_unb64(encoded_signature), f"{encoded_header}.{encoded_payload}".encode("ascii"))
        except (InvalidSignature, ValueError) as exc:
            raise IdentityError("Identity assertion signature is invalid.") from exc
        if set(payload) != CLAIMS:
            raise IdentityError("Identity assertion claims are malformed.")
        if payload.get("iss") != issuer or payload.get("aud") != audience or payload.get("token_use") != token_use:
            raise IdentityError("Identity assertion issuer, audience, or use is invalid.")
        for field in ("sub", "preferred_username", "jti"):
            if not isinstance(payload.get(field), str) or not SAFE_VALUE.fullmatch(payload[field]):
                raise IdentityError("Identity assertion contains an invalid claim.")
        for field in ("roles", "scope"):
            values = payload.get(field)
            if not isinstance(values, list) or len(values) > 20 or len(values) != len(set(values)):
                raise IdentityError("Identity assertion roles or scopes are invalid.")
            if any(not isinstance(value, str) or not SAFE_VALUE.fullmatch(value) for value in values):
                raise IdentityError("Identity assertion roles or scopes are invalid.")
        if not all(isinstance(payload.get(field), int) and not isinstance(payload[field], bool)
                   for field in ("iat", "nbf", "exp")):
            raise IdentityError("Identity assertion times are invalid.")
        current = int(time.time()) if now is None else now
        lifetime = payload["exp"] - payload["iat"]
        if not 30 <= lifetime <= 60 or payload["nbf"] > current + 5 or payload["iat"] > current + 5 or payload["exp"] <= current:
            raise IdentityError("Identity assertion is expired or outside its allowed lifetime.")
        if required_scopes and not required_scopes.issubset(payload["scope"]):
            raise IdentityError("Identity assertion lacks a required scope.")
        if replay_guard:
            replay_guard.check_and_mark(payload["jti"], payload["exp"], current)
        return payload


def generate_key_files(private_path: Path, public_path: Path, *, kid: str) -> None:
    if private_path.exists() or public_path.exists():
        raise IdentityError("Refusing to overwrite an identity key file.")
    if not SAFE_VALUE.fullmatch(kid):
        raise IdentityError("Identity key ID is invalid.")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    private_path.write_bytes(private)
    if os.name != "nt":
        private_path.chmod(0o600)
    public_path.write_text(json.dumps({"keys": [{
        "alg": ALGORITHM, "crv": "Ed25519", "kid": kid, "kty": "OKP",
        "use": "sig", "x": _b64(public),
    }]}, indent=2) + "\n", encoding="utf-8")
