from __future__ import annotations

import json
import subprocess

import pytest
from sqlalchemy import select

from foxden_music.enums import AcquisitionProvider, AcquisitionSourceType, AcquisitionState, PreferredFormat
from foxden_music.models import AcquisitionJob
from foxden_music.request_workflow import (
    RequestReference,
    create_request_jobs,
    parse_request_batch,
    parse_request_reference,
    resolve_next_request,
    resolve_reference,
)
from foxden_music.fingerprint import fingerprint_audio
from foxden_music.providers import ProviderAdapterError, provider_adapter


RELEASE_ID = "f21c2200-85ae-4aaa-94d9-e80079a1e705"
RECORDING_ID = "297dfc0d-5fec-7b20-1653-d1857ca4b580"


def release_payload() -> dict:
    return {
        "id": RELEASE_ID,
        "title": "Den Songs",
        "date": "2024-10-15",
        "country": "US",
        "status": "Official",
        "artist-credit": [{"name": "Fox Artist", "joinphrase": ""}],
        "media": [{
            "position": 1,
            "tracks": [{
                "position": 1,
                "title": "Night Run",
                "length": 180000,
                "recording": {
                    "id": RECORDING_ID,
                    "title": "Night Run",
                    "length": 180000,
                    "isrcs": ["USFOX2400001"],
                    "artist-credit": [{"name": "Fox Artist", "joinphrase": ""}],
                },
            }],
        }],
    }


class FakeMusicBrainz:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def lookup_release(self, release_id: str):
        assert release_id == RELEASE_ID
        return release_payload()


def test_request_parser_accepts_names_spotify_and_musicbrainz() -> None:
    song = parse_request_reference("Fox Artist - Night Run")
    assert song.source_type is AcquisitionSourceType.RECORDING
    assert song.artist == "Fox Artist"
    assert song.title == "Night Run"

    album = parse_request_reference("Den Songs", request_type="ALBUM", artist="Fox Artist")
    assert album.source_type is AcquisitionSourceType.ALBUM
    assert album.artist == "Fox Artist"

    spotify = parse_request_reference("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=discarded")
    assert spotify.canonical_input == "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

    release = parse_request_reference(f"https://musicbrainz.org/release/{RELEASE_ID}")
    assert release.source_type is AcquisitionSourceType.RELEASE
    assert release.identifier == RELEASE_ID


@pytest.mark.parametrize(
    "value",
    [
        "http://musicbrainz.org/release/" + RELEASE_ID,
        "https://evil.example/release/" + RELEASE_ID,
        "https://musicbrainz.org/release/not-a-uuid",
        "https://open.spotify.com/episode/37i9dQZF1DXcBWIGoYBM5M",
    ],
)
def test_request_parser_rejects_unsafe_or_unsupported_links(value: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_request_reference(value)


def test_direct_musicbrainz_release_builds_canonical_manifest(settings) -> None:
    reference = RequestReference(
        AcquisitionSourceType.RELEASE,
        f"https://musicbrainz.org/release/{RELEASE_ID}",
        RELEASE_ID,
    )
    result = resolve_reference(reference, settings, FakeMusicBrainz())

    assert result.confidence == 100
    assert result.needs_user is False
    assert result.manifest["release_id"] == RELEASE_ID
    assert result.manifest["album_edition"]["title"] == "Den Songs"
    assert result.manifest["expected_tracks"][0] == {
        "disc_number": 1,
        "track_number": 1,
        "title": "Night Run",
        "artist": "Fox Artist",
        "recording_id": RECORDING_ID,
        "isrcs": ["USFOX2400001"],
        "duration_seconds": 180.0,
    }


def test_resolver_advances_request_and_persists_manifest(database, settings) -> None:
    inbox = settings.staging_dir / "request-downloads"
    inbox.mkdir()
    settings = settings.model_copy(
        update={
            "music_request_provider_url": "https://provider.example/",
            "download_inbox_dir": inbox,
        }
    )
    with database.session() as session:
        request = create_request_jobs(
            session,
            [parse_request_reference(f"https://musicbrainz.org/release/{RELEASE_ID}")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        request_id = request.id

    resolved_id = resolve_next_request(database, settings, mb_factory=FakeMusicBrainz)
    assert resolved_id == request_id

    with database.session() as session:
        request = session.get(AcquisitionJob, request_id)
        assert request is not None
        assert request.state == AcquisitionState.WAITING_FOR_USER.value
        assert request.confidence == 100
        assert json.loads(request.manifest_json or "{}")["release_id"] == RELEASE_ID
        assert [event.state for event in request.events] == [
            AcquisitionState.REQUESTED.value,
            AcquisitionState.RESOLVING.value,
            AcquisitionState.WAITING_FOR_USER.value,
        ]


def test_batch_deduplicates_and_playlist_children_are_independent(database) -> None:
    refs = parse_request_batch(
        "\n".join(
            [
                f"https://musicbrainz.org/release/{RELEASE_ID}",
                f"https://musicbrainz.org/release/{RELEASE_ID}",
                "Fox Artist - Night Run",
            ]
        )
    )
    with database.session() as session:
        parent = create_request_jobs(
            session,
            refs[:1],
            preferred_format=PreferredFormat.MP3_320,
            provider=AcquisitionProvider.FILESYSTEM_DROP,
        )[0]
        children = create_request_jobs(
            session,
            refs[1:],
            preferred_format=PreferredFormat.MP3_320,
            provider=AcquisitionProvider.FILESYSTEM_DROP,
            parent_request_id=parent.id,
        )
        assert len(children) == 1
        child_id = children[0].id

    with database.session() as session:
        child = session.scalar(select(AcquisitionJob).where(AcquisitionJob.id == child_id))
        assert child is not None
        assert child.parent_request_id == parent.id
        assert child.state == AcquisitionState.REQUESTED.value


def test_spotify_playlist_follows_safe_pagination(settings) -> None:
    class FakeSpotify:
        def __init__(self):
            self.followed: list[str] = []

        def get(self, path: str):
            assert path.startswith("playlists/")
            return {
                "items": [{"track": {"id": "0VjIjW4GlUZAMYd2vXMi3b", "name": "First", "artists": [{"name": "Fox"}]}}],
                "next": "https://api.spotify.com/v1/playlists/list/tracks?offset=100",
            }

        def get_url(self, url: str):
            self.followed.append(url)
            return {
                "items": [{"track": {"id": "1ATL5GLyefJaxhQzSPVrLX", "name": "Second", "artists": [{"name": "Fox"}]}}],
                "next": None,
            }

    spotify = FakeSpotify()
    reference = parse_request_reference(
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    )
    result = resolve_reference(reference, settings, FakeMusicBrainz(), spotify=spotify)

    assert result.manifest["child_count"] == 2
    assert [child.title for child in result.children] == ["First", "Second"]
    assert spotify.followed == [
        "https://api.spotify.com/v1/playlists/list/tracks?offset=100"
    ]


def test_optional_chromaprint_and_acoustid_adapter(monkeypatch, settings, tmp_path) -> None:
    audio = tmp_path / "track.flac"
    audio.write_bytes(b"synthetic")
    configured = settings.model_copy(
        update={"chromaprint_enabled": True, "acoustid_api_key": "test-key"}
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=json.dumps({"duration": 180.2, "fingerprint": "abc123"}), stderr=""
        ),
    )

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"results": [{"recordings": [{"id": RECORDING_ID}]}]}

    monkeypatch.setattr("foxden_music.fingerprint.httpx.get", lambda *args, **kwargs: Response())
    evidence = fingerprint_audio(audio, configured)

    assert evidence["duration"] == 180
    assert evidence["mode"] == "acoustid"
    assert evidence["acoustid_recording_ids"] == [RECORDING_ID]


def test_provider_adapters_are_configured_and_request_scoped(database, settings, tmp_path) -> None:
    inbox = tmp_path / "downloads"
    inbox.mkdir()
    configured = settings.model_copy(
        update={
            "download_inbox_dir": inbox,
            "music_request_provider_url": "https://provider.example/music",
        }
    )
    with database.session() as session:
        request = create_request_jobs(
            session,
            [parse_request_reference(f"https://musicbrainz.org/release/{RELEASE_ID}")],
            preferred_format=PreferredFormat.FLAC,
            provider=AcquisitionProvider.MANUAL_BROWSER,
        )[0]
        request_id = request.id
        handoff = provider_adapter(AcquisitionProvider.MANUAL_BROWSER).prepare(request, configured)
        assert handoff.requires_user is True
        assert handoff.public_url == "https://provider.example/music"
        assert handoff.download_directory == inbox / request_id

    invalid = configured.model_copy(update={"music_request_provider_url": "http://provider.example/"})
    with database.session() as session:
        request = session.get(AcquisitionJob, request_id)
        assert request is not None
        with pytest.raises(ProviderAdapterError):
            provider_adapter(AcquisitionProvider.MANUAL_BROWSER).prepare(request, invalid)
