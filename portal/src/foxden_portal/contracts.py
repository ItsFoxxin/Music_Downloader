from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTRACT_VERSION = "1.0"
IDENTITY_HEADER = "X-FoxDen-Identity"


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    label: str = Field(min_length=1, max_length=120)
    enabled: bool


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["healthy", "unhealthy"]
    summary: str = Field(min_length=1, max_length=200)


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=60)
    occurred_at: datetime
    path: str | None = Field(default=None, max_length=300)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("/") or value.startswith("//") or ".." in value):
            raise ValueError("path must be a safe relative application path")
        return value


class ModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    contract_version: Literal["1.0"]
    module_id: str = Field(min_length=1, max_length=40)
    module_name: str = Field(min_length=1, max_length=80)
    module_version: str = Field(min_length=1, max_length=40)
    health: Health
    capabilities: list[Capability] = Field(max_length=50)
    activity: list[Activity] = Field(max_length=20)


class IdentityError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_identity_assertion(
    *, secret: str, issuer: str, audience: str, subject: str, username: str,
    roles: list[str], lifetime_seconds: int = 60, now: int | None = None,
) -> str:
    timestamp = int(time.time()) if now is None else now
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "preferred_username": username,
        "roles": sorted(set(roles)),
        "iat": timestamp,
        "nbf": timestamp - 2,
        "exp": timestamp + lifetime_seconds,
        "jti": secrets.token_urlsafe(16),
    }
    encoded = f"{_b64(json.dumps(header, separators=(',', ':'), sort_keys=True).encode())}.{_b64(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode())}"
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def verify_identity_assertion(
    token: str, *, secret: str, issuer: str, audience: str, now: int | None = None,
) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_unb64(encoded_header))
        payload = json.loads(_unb64(encoded_payload))
        supplied = _unb64(encoded_signature)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise IdentityError("Malformed internal identity assertion.") from exc
    if header != {"alg": "HS256", "typ": "JWT"}:
        raise IdentityError("Unsupported internal identity assertion header.")
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, supplied):
        raise IdentityError("Invalid internal identity assertion signature.")
    timestamp = int(time.time()) if now is None else now
    required = {"iss", "aud", "sub", "preferred_username", "roles", "iat", "nbf", "exp", "jti"}
    if set(payload) != required:
        raise IdentityError("Internal identity assertion claims are incomplete.")
    if payload["iss"] != issuer or payload["aud"] != audience:
        raise IdentityError("Internal identity assertion issuer or audience is invalid.")
    if not isinstance(payload["roles"], list) or any(not isinstance(role, str) for role in payload["roles"]):
        raise IdentityError("Internal identity assertion roles are invalid.")
    if not all(isinstance(payload[key], int) for key in ("iat", "nbf", "exp")):
        raise IdentityError("Internal identity assertion times are invalid.")
    if payload["nbf"] > timestamp + 5 or payload["exp"] <= timestamp or payload["exp"] - payload["iat"] > 300:
        raise IdentityError("Internal identity assertion is expired or outside its allowed lifetime.")
    return payload
