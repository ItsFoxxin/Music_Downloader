from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from foxden import ConfigError
from migration import create_backup, inventory, readiness, restore_rehearsal, verify_backup


def fixture_values(tmp_path: Path) -> dict[str, str]:
    music = tmp_path / "live-fixture" / "music-config"
    qbit = tmp_path / "live-fixture" / "qbittorrent-config"
    music.mkdir(parents=True)
    qbit.mkdir(parents=True)
    (music / "foxden-music.db").write_bytes(b"synthetic-sqlite-state")
    (qbit / "BT_backup").mkdir()
    (qbit / "BT_backup" / "example.fastresume").write_bytes(b"synthetic-resume-state")
    return {"MUSIC_CONFIG_PATH": str(music), "QBIT_CONFIG_PATH": str(qbit)}


def test_inventory_is_read_only_and_excludes_contents(tmp_path: Path) -> None:
    report = inventory(fixture_values(tmp_path))
    assert report["read_only"] is True
    assert {entry["role"] for entry in report["entries"]} == {"music-config", "qbittorrent-config"}
    assert "synthetic-sqlite-state" not in str(report)


def test_backup_requires_writer_stop_confirmation(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="writers-stopped"):
        create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=False)


def test_backup_verify_and_isolated_restore_round_trip(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=True)
    assert archive is not None and verify_backup(archive)
    restore = tmp_path / "restore"
    restore_rehearsal(archive, restore, execute=True)
    assert (restore / "music-config" / "foxden-music.db").read_bytes() == b"synthetic-sqlite-state"
    assert (restore / "qbittorrent-config" / "BT_backup" / "example.fastresume").exists()


def test_restore_refuses_nonempty_destination(tmp_path: Path) -> None:
    archive = create_backup(fixture_values(tmp_path), tmp_path / "backups", execute=True, writers_stopped=True)
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ConfigError, match="empty"):
        restore_rehearsal(archive, destination, execute=True)


def test_large_data_roots_are_inventory_only_and_not_backed_up(tmp_path: Path) -> None:
    values = fixture_values(tmp_path)
    library = tmp_path / "media-library"
    library.mkdir()
    (library / "large-placeholder.mkv").write_bytes(b"fixture")
    values["MEDIA_LIBRARY_PATH"] = str(library)

    report = inventory(values)
    media = next(entry for entry in report["entries"] if entry["role"] == "media-library")
    assert media["content_scan"] == "skipped-large-data-root"
    archive = create_backup(values, tmp_path / "backups", execute=True, writers_stopped=True)
    assert archive is not None
    restore = tmp_path / "restore-large"
    restore_rehearsal(archive, restore, execute=True)
    assert not (restore / "media-library").exists()
