from pathlib import Path

import pytest

from app.config import Settings


def test_settings_load_secret_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    password = tmp_path / "qbit-password"
    token = tmp_path / "app-token"
    password.write_text("qbit-secret\n", encoding="utf-8")
    token.write_text("a-long-random-application-token\n", encoding="utf-8")
    monkeypatch.delenv("QBIT_PASSWORD", raising=False)
    monkeypatch.delenv("APP_TOKEN", raising=False)
    monkeypatch.setenv("QBIT_PASSWORD_FILE", str(password))
    monkeypatch.setenv("APP_TOKEN_FILE", str(token))

    settings = Settings()

    assert settings.qbit_password == "qbit-secret"
    assert settings.token == "a-long-random-application-token"


def test_settings_rejects_ambiguous_secret_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("APP_TOKEN", "from-environment")
    monkeypatch.setenv("APP_TOKEN_FILE", str(secret))

    with pytest.raises(ValueError, match="either APP_TOKEN or APP_TOKEN_FILE"):
        Settings()
