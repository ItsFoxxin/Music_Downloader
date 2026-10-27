from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.lower() not in {"true", "false"}:
        raise ConfigError(f"{name} must be true or false.")
    return raw.lower() == "true"


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _floating(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _secret(name: str, *, required: bool = False, minimum: int = 32) -> str | None:
    direct = os.getenv(name)
    file_name = os.getenv(name + "_FILE")
    if direct and file_name:
        raise ConfigError(f"Set only one of {name} or {name}_FILE.")
    value = direct
    if file_name:
        path = Path(file_name)
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(f"{name}_FILE is not readable.") from exc
    if value is not None:
        value = value.strip()
    if required and not value:
        raise ConfigError(f"Set {name} or {name}_FILE.")
    if value and len(value) < minimum:
        raise ConfigError(f"{name} must contain at least {minimum} characters.")
    return value or None


@dataclass(frozen=True)
class ModuleConfig:
    module_id: str
    name: str
    base_url: str
    navigation_path: str
    enabled: bool = True


@dataclass(frozen=True)
class Settings:
    database_path: Path
    public_url: str
    secret_key: str
    bootstrap_secret: str | None
    bootstrap_expires_seconds: int
    auth_mode: str
    cookie_secure: bool
    session_seconds: int
    login_max_attempts: int
    login_window_seconds: int
    login_lock_seconds: int
    module_timeout_seconds: float
    modules: tuple[ModuleConfig, ...]
    oidc_issuer: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_redirect_uri: str | None
    oidc_scopes: tuple[str, ...]
    oidc_allowed_groups: tuple[str, ...]
    oidc_admin_groups: tuple[str, ...]
    oidc_logout: str
    identity_private_key_path: Path | None
    identity_signing_kid: str
    identity_issuer: str
    identity_lifetime_seconds: int

    @property
    def local_enabled(self) -> bool:
        return self.auth_mode in {"local", "hybrid"}

    @property
    def oidc_enabled(self) -> bool:
        return self.auth_mode in {"oidc", "hybrid"}

    @classmethod
    def from_env(cls) -> "Settings":
        public_url = os.getenv("PORTAL_PUBLIC_URL", "http://localhost:8020").rstrip("/")
        parsed = urlsplit(public_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ConfigError("PORTAL_PUBLIC_URL must be an HTTP(S) URL without credentials.")
        auth_mode = os.getenv("PORTAL_AUTH_MODE", "local").lower()
        if auth_mode not in {"local", "oidc", "hybrid"}:
            raise ConfigError("PORTAL_AUTH_MODE must be local, oidc, or hybrid.")

        modules = _modules_from_env()
        issuer = os.getenv("PORTAL_OIDC_ISSUER", "").rstrip("/") or None
        client_id = os.getenv("PORTAL_OIDC_CLIENT_ID", "").strip() or None
        client_secret = _secret("PORTAL_OIDC_CLIENT_SECRET", minimum=16)
        redirect_uri = os.getenv("PORTAL_OIDC_REDIRECT_URI", "").strip() or f"{public_url}/auth/oidc/callback"
        if auth_mode in {"oidc", "hybrid"}:
            if not issuer or not client_id or not client_secret:
                raise ConfigError("OIDC mode requires PORTAL_OIDC_ISSUER, PORTAL_OIDC_CLIENT_ID, and a client secret.")
            ip = urlsplit(issuer)
            if ip.scheme != "https" or not ip.hostname or ip.username or ip.password:
                raise ConfigError("PORTAL_OIDC_ISSUER must be an HTTPS URL without credentials.")
            rp = urlsplit(redirect_uri)
            local = rp.hostname in {"localhost", "127.0.0.1", "::1"}
            if rp.scheme not in ({"http", "https"} if local else {"https"}) or not rp.hostname:
                raise ConfigError("PORTAL_OIDC_REDIRECT_URI must use HTTPS except on localhost.")

        scopes = tuple(dict.fromkeys(os.getenv("PORTAL_OIDC_SCOPES", "openid profile email").split()))
        if "openid" not in scopes:
            raise ConfigError("PORTAL_OIDC_SCOPES must include openid.")
        oidc_logout = os.getenv("PORTAL_OIDC_LOGOUT", "local").lower()
        if oidc_logout not in {"local", "provider"}:
            raise ConfigError("PORTAL_OIDC_LOGOUT must be local or provider.")

        settings = cls(
            database_path=Path(os.getenv("PORTAL_DATABASE_PATH", "/config/portal.db")).absolute(),
            public_url=public_url,
            secret_key=_secret("PORTAL_SECRET_KEY", required=True, minimum=32) or "",
            bootstrap_secret=_secret("PORTAL_BOOTSTRAP_SECRET", minimum=32),
            bootstrap_expires_seconds=_integer("PORTAL_BOOTSTRAP_EXPIRES_SECONDS", 3600, 300, 86400),
            auth_mode=auth_mode,
            cookie_secure=_boolean("PORTAL_COOKIE_SECURE", parsed.scheme == "https"),
            session_seconds=_integer("PORTAL_SESSION_SECONDS", 28800, 300, 604800),
            login_max_attempts=_integer("PORTAL_LOGIN_MAX_ATTEMPTS", 5, 2, 50),
            login_window_seconds=_integer("PORTAL_LOGIN_WINDOW_SECONDS", 900, 60, 86400),
            login_lock_seconds=_integer("PORTAL_LOGIN_LOCK_SECONDS", 900, 60, 86400),
            module_timeout_seconds=_floating("PORTAL_MODULE_TIMEOUT_SECONDS", 1.5, 0.1, 10.0),
            modules=modules,
            oidc_issuer=issuer,
            oidc_client_id=client_id,
            oidc_client_secret=client_secret,
            oidc_redirect_uri=redirect_uri if auth_mode in {"oidc", "hybrid"} else None,
            oidc_scopes=scopes,
            oidc_allowed_groups=_csv("PORTAL_OIDC_ALLOWED_GROUPS"),
            oidc_admin_groups=_csv("PORTAL_OIDC_ADMIN_GROUPS"),
            oidc_logout=oidc_logout,
            identity_private_key_path=(Path(os.environ["PORTAL_IDENTITY_PRIVATE_KEY_FILE"]).absolute()
                                       if os.getenv("PORTAL_IDENTITY_PRIVATE_KEY_FILE") else None),
            identity_signing_kid=os.getenv("PORTAL_IDENTITY_SIGNING_KID", "foxden-portal-1").strip(),
            identity_issuer=os.getenv("PORTAL_IDENTITY_ISSUER", "foxden-portal").strip(),
            identity_lifetime_seconds=_integer("PORTAL_IDENTITY_LIFETIME_SECONDS", 45, 30, 60),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        for name, value in (("PORTAL_IDENTITY_ISSUER", self.identity_issuer),
                            ("PORTAL_IDENTITY_SIGNING_KID", self.identity_signing_kid)):
            if not value or len(value) > 100:
                raise ConfigError(f"{name} must be 1 to 100 characters.")
        if self.identity_private_key_path and not self.identity_private_key_path.is_file():
            raise ConfigError("PORTAL_IDENTITY_PRIVATE_KEY_FILE is not readable.")
        if self.local_enabled and not self.bootstrap_secret and not self.database_path.exists():
            raise ConfigError("A fresh local-auth deployment requires PORTAL_BOOTSTRAP_SECRET or its file form.")
        if self.auth_mode == "oidc" and not self.oidc_admin_groups:
            raise ConfigError("OIDC-only mode requires PORTAL_OIDC_ADMIN_GROUPS so an administrator can be identified.")
        if len({module.module_id for module in self.modules}) != len(self.modules):
            raise ConfigError("PORTAL_MODULES_JSON contains duplicate module IDs.")

    def redacted(self) -> dict:
        return {
            "public_url": self.public_url,
            "database_path": "configured",
            "auth_mode": self.auth_mode,
            "cookie_secure": self.cookie_secure,
            "oidc_configured": self.oidc_enabled,
            "bootstrap_configured": bool(self.bootstrap_secret),
            "identity_signing_configured": bool(self.identity_private_key_path),
            "modules": [{"id": m.module_id, "name": m.name, "enabled": m.enabled} for m in self.modules],
        }


def _csv(name: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, "").split(",") if value.strip())


def _modules_from_env() -> tuple[ModuleConfig, ...]:
    raw = os.getenv("PORTAL_MODULES_JSON", "[]")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError("PORTAL_MODULES_JSON must be valid JSON.") from exc
    if not isinstance(values, list) or len(values) > 20:
        raise ConfigError("PORTAL_MODULES_JSON must be a list of at most 20 modules.")
    modules: list[ModuleConfig] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise ConfigError(f"Module {index} must be an object.")
        module_id = str(value.get("id", "")).strip()
        name = str(value.get("name", "")).strip()
        base_url = str(value.get("base_url", "")).rstrip("/")
        navigation_path = str(value.get("navigation_path", "")).strip()
        enabled = value.get("enabled", True)
        if not module_id or not module_id.replace("-", "").isalnum() or len(module_id) > 40:
            raise ConfigError(f"Module {index} has an invalid id.")
        if not name or len(name) > 80:
            raise ConfigError(f"Module {module_id} has an invalid name.")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ConfigError(f"Module {module_id} base_url must be HTTP(S) without credentials.")
        if not navigation_path.startswith("/") or navigation_path.startswith("//") or ".." in navigation_path:
            raise ConfigError(f"Module {module_id} navigation_path must be a safe absolute path.")
        if not isinstance(enabled, bool):
            raise ConfigError(f"Module {module_id} enabled must be true or false.")
        modules.append(ModuleConfig(module_id, name, base_url, navigation_path, enabled))
    return tuple(modules)
