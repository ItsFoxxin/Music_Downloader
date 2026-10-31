from pathlib import Path

import pytest
from pydantic import ValidationError

from foxden_music.config import Settings


def test_settings_load_secret_files(tmp_path: Path) -> None:
    csrf = tmp_path / "csrf"
    jellyfin = tmp_path / "jellyfin"
    csrf.write_text("csrf-secret-value\n", encoding="utf-8")
    jellyfin.write_text("jellyfin-secret-value\n", encoding="utf-8")

    settings = Settings(csrf_secret_file=csrf, jellyfin_api_key_file=jellyfin)

    assert settings.csrf_secret == "csrf-secret-value"
    assert settings.jellyfin_api_key == "jellyfin-secret-value"


def test_settings_rejects_ambiguous_secret_source(tmp_path: Path) -> None:
    csrf = tmp_path / "csrf"
    csrf.write_text("from-file", encoding="utf-8")

    with pytest.raises(ValidationError, match="either CSRF_SECRET or CSRF_SECRET_FILE"):
        Settings(csrf_secret="from-environment", csrf_secret_file=csrf)


def test_settings_rejects_empty_secret_file(tmp_path: Path) -> None:
    csrf = tmp_path / "csrf"
    csrf.write_text("\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="CSRF_SECRET_FILE is empty"):
        Settings(csrf_secret_file=csrf)
