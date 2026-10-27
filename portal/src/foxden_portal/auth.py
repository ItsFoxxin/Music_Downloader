from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import Settings
from .database import PortalStore


USERNAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,39}$")


class AuthError(ValueError):
    pass


class RateLimited(AuthError):
    def __init__(self, retry_after: int):
        super().__init__("Too many login attempts. Try again later.")
        self.retry_after = retry_after


class AuthService:
    def __init__(self, settings: Settings, store: PortalStore):
        self.settings = settings
        self.store = store
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
        self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))

    def normalize_username(self, value: str) -> str:
        username = value.strip().lower()
        if not USERNAME.fullmatch(username):
            raise AuthError("Username must be 3 to 40 letters, numbers, dots, underscores, or hyphens.")
        return username

    @staticmethod
    def validate_password(password: str) -> None:
        if not 12 <= len(password) <= 256:
            raise AuthError("Password must contain 12 to 256 characters.")
        categories = sum((any(c.islower() for c in password), any(c.isupper() for c in password),
                          any(c.isdigit() for c in password), any(not c.isalnum() for c in password)))
        if categories < 3:
            raise AuthError("Password must use at least three of: lowercase, uppercase, numbers, symbols.")

    def create_initial_admin(self, bootstrap: str, username: str, display_name: str, password: str) -> dict:
        if not self.settings.local_enabled:
            raise AuthError("Local authentication is disabled.")
        if not self.settings.bootstrap_secret:
            raise AuthError("Initial setup is not available until a bootstrap secret is configured.")
        if self.store.bootstrap_used() or self.store.has_admin():
            raise AuthError("Initial administrator setup is already complete.")
        age = int(time.time()) - self.store.first_started_at()
        if age > self.settings.bootstrap_expires_seconds:
            raise AuthError("The bootstrap window expired. Rotate the bootstrap secret using the documented recovery procedure.")
        if not hmac.compare_digest(bootstrap.encode(), self.settings.bootstrap_secret.encode()):
            raise AuthError("Bootstrap credentials are invalid.")
        username = self.normalize_username(username)
        self.validate_password(password)
        display_name = display_name.strip() or username
        if len(display_name) > 100:
            raise AuthError("Display name is too long.")
        return self.store.claim_first_admin(username, display_name, self.hasher.hash(password))

    def create_user(self, username: str, display_name: str, password: str, role: str = "user") -> dict:
        username = self.normalize_username(username)
        self.validate_password(password)
        display_name = display_name.strip() or username
        if len(display_name) > 100:
            raise AuthError("Display name is too long.")
        return self.store.create_local_user(username, display_name, self.hasher.hash(password), role)

    def login(self, username: str, password: str, client_key: str) -> dict:
        retry_after = self.store.rate_limited(client_key)
        if retry_after:
            raise RateLimited(retry_after)
        try:
            normalized = self.normalize_username(username)
        except AuthError:
            normalized = "invalid-user"
        user = self.store.user_by_username(normalized)
        encoded = user.get("password_hash") if user else self._dummy_hash
        valid = False
        try:
            valid = bool(encoded) and self.hasher.verify(encoded, password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not valid or not user or not user["active"]:
            self.store.record_failure(client_key, self.settings.login_max_attempts,
                                      self.settings.login_window_seconds, self.settings.login_lock_seconds)
            raise AuthError("Username or password is incorrect.")
        self.store.clear_failures(client_key)
        if self.hasher.check_needs_rehash(encoded):
            self.store.update_password(user["username"], self.hasher.hash(password))
        return user

    def set_password(self, username: str, password: str) -> None:
        username = self.normalize_username(username)
        self.validate_password(password)
        self.store.update_password(username, self.hasher.hash(password))

    def preauth_csrf(self) -> str:
        value = secrets.token_urlsafe(32)
        signature = hmac.new(self.settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()
        return f"{value}.{signature}"

    def verify_preauth_csrf(self, value: str | None) -> bool:
        if not value:
            return False
        try:
            token, supplied = value.rsplit(".", 1)
        except ValueError:
            return False
        expected = hmac.new(self.settings.secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, supplied)
