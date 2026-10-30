"""Release-only tests: real ffmpeg, ffprobe, Mutagen and atomic publication."""
import io
import os
import re
import shutil
import subprocess
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from foxden_music.audio import sha256_file
from foxden_music.metadata import NormalizedTrackMetadata, read_tag_hints, write_tags
from foxden_music.models import Job, LibraryTrack
from foxden_music.pipeline import process_job
from foxden_music.web import create_app

pytestmark = pytest.mark.integration


def test_real_album_upload_tag_publish_and_duplicate(settings, database, tmp_path):
    settings.ffmpeg_path = os.environ.get("FFMPEG_PATH", "ffmpeg")
    settings.ffprobe_path = os.environ.get("FFPROBE_PATH", "ffprobe")
    # Fail, don't skip, when a release runner lacks the real tools.
    assert shutil.which(settings.ffmpeg_path), "Install ffmpeg for integration tests"
    assert shutil.which(settings.ffprobe_path), "Install ffprobe for integration tests"
    settings.musicbrainz_contact = None
    settings.jellyfin_url = None
    settings.jellyfin_api_key = None
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        for number, title in [(1, "여우별"), (2, "Café at Dawn")]:
            audio = tmp_path / f"{number}.flac"
            subprocess.run([settings.ffmpeg_path, "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"sine=frequency={440+number*50}:duration=2",
                "-c:a", "flac", str(audio)], check=True, timeout=30)
            write_tags(audio, NormalizedTrackMetadata(title=title, artist="CI Artist",
                album_artist="CI Artist", album="Signals", track_number=number,
                track_total=2, disc_number=1, disc_total=1, release_date="2026-10-14",
                year=2026), None)
            output.write(audio, f"{number:02d} - {title}.flac")
    payload = archive.getvalue()
    original_hashes = None
    with TestClient(create_app(settings, database)) as client:
        for attempt in range(2):
            token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/add").text)[1]
            response = client.post("/imports", data={"csrf_token": token},
                files={"album": ("signals.zip", payload, "application/zip")}, follow_redirects=False)
            assert response.status_code == 303, response.text
            job_id = response.headers["location"].rsplit("/", 1)[-1]
            with database.session() as session:
                job = session.get(Job, job_id)
                job.selected_release_id = "__incoming__"
                job.state = "STAGING"
                source = settings.jobs_dir / job.id / job.source_relative_path
                session.commit()
            source_hash = sha256_file(source)
            process_job(database, settings, job_id)
            with database.session() as session:
                job = session.get(Job, job_id)
                assert job.state == "COMPLETE", (job.state, job.review_reason, job.error_message)
                assert job.imported_count == (2 if attempt == 0 else 0)
                assert job.skipped_count == (0 if attempt == 0 else 2)
                tracks = session.scalars(select(LibraryTrack)).all()
                assert len(tracks) == 2
                paths = [settings.music_dir / track.final_relative_path for track in tracks]
            assert sha256_file(source) == source_hash, "Staged originals must remain unchanged"
            assert {read_tag_hints(path).title for path in paths} == {"여우별", "Café at Dawn"}
            assert all(read_tag_hints(path).year == 2026 for path in paths)
            hashes = {path.relative_to(settings.music_dir).as_posix(): sha256_file(path) for path in paths}
            if original_hashes is not None:
                assert hashes == original_hashes, "Duplicate import must not rewrite existing music"
            original_hashes = hashes
