from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, update

from .acquisition import add_acquisition_event, transition_acquisition
from .cache import DatabaseJsonCache
from .config import Settings
from .database import Database
from .enums import AcquisitionProvider, AcquisitionSourceType, AcquisitionState, PreferredFormat
from .models import AcquisitionJob
from .musicbrainz import AlbumHints, MusicBrainzClient, TrackHint
from .providers import ProviderAdapterError, provider_adapter


_PAIR = re.compile(r"^\s*(?P<artist>.+?)\s*(?:::|\s+-\s+)\s*(?P<title>.+?)\s*$")
_RISKY_EDITION_WORDS = ("live", "remaster", "deluxe", "clean", "explicit", "compilation")


class RequestResolutionError(RuntimeError):
    pass


class WaitingForUser(RequestResolutionError):
    pass


@dataclass(frozen=True, slots=True)
class RequestReference:
    source_type: AcquisitionSourceType
    canonical_input: str
    identifier: str
    artist: str | None = None
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    manifest: Mapping[str, Any]
    confidence: float
    reasons: tuple[str, ...]
    needs_user: bool = False
    required_action: str | None = None
    children: tuple[RequestReference, ...] = ()


def parse_request_reference(
    value: str, *, request_type: str = "AUTO", artist: str | None = None
) -> RequestReference:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2_048 or any(ord(char) < 0x20 for char in raw):
        raise ValueError("Each request must contain safe text between 1 and 2,048 characters")
    if raw.startswith(("http://", "https://")):
        parsed = urlsplit(raw)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
            raise ValueError("Music links must be canonical HTTPS URLs without credentials or ports")
        host = (parsed.hostname or "").casefold()
        parts = [part for part in parsed.path.split("/") if part]
        if host == "open.spotify.com" and len(parts) == 2 and parts[0] in {"track", "album", "playlist"}:
            if not re.fullmatch(r"[A-Za-z0-9]{22}", parts[1]):
                raise ValueError("Spotify link contains an invalid identifier")
            return RequestReference(
                AcquisitionSourceType(parts[0].upper()),
                f"https://open.spotify.com/{parts[0]}/{parts[1]}",
                parts[1],
            )
        if host == "musicbrainz.org" and len(parts) == 2 and parts[0] in {"recording", "release"}:
            identifier = str(uuid.UUID(parts[1]))
            kind = AcquisitionSourceType.RECORDING if parts[0] == "recording" else AcquisitionSourceType.RELEASE
            return RequestReference(kind, f"https://musicbrainz.org/{parts[0]}/{identifier}", identifier)
        raise ValueError("Use a Spotify track/album/playlist or MusicBrainz recording/release link")

    normalized_type = request_type.strip().upper()
    if normalized_type == "ARTIST":
        return RequestReference(AcquisitionSourceType.ARTIST, raw, raw, artist=raw)
    pair = _PAIR.fullmatch(raw)
    resolved_artist = (artist or (pair.group("artist") if pair else "")).strip()
    title = (pair.group("title") if pair else raw).strip()
    if normalized_type not in {"AUTO", "TRACK", "ALBUM", "RECORDING"}:
        raise ValueError("Request type must be auto, track, album, or artist")
    if not resolved_artist:
        raise ValueError("Use 'Artist - Title' or provide an artist")
    kind = AcquisitionSourceType.ALBUM if normalized_type == "ALBUM" else AcquisitionSourceType.RECORDING
    return RequestReference(kind, raw, raw, artist=resolved_artist, title=title)


def parse_request_batch(
    value: str, *, request_type: str = "AUTO", artist: str | None = None, max_items: int = 100
) -> list[RequestReference]:
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("Enter at least one music request")
    if len(lines) > max_items:
        raise ValueError(f"A batch may contain at most {max_items} requests")
    result: list[RequestReference] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        try:
            item = parse_request_reference(line, request_type=request_type, artist=artist)
        except ValueError as exc:
            raise ValueError(f"Line {number}: {exc}") from exc
        if item.canonical_input not in seen:
            result.append(item)
            seen.add(item.canonical_input)
    return result


def _artist_credit(value: object) -> str:
    if not isinstance(value, list):
        return ""
    result: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        artist = item.get("artist") if isinstance(item.get("artist"), Mapping) else {}
        result.append(str(item.get("name") or artist.get("name") or ""))
        result.append(str(item.get("joinphrase") or ""))
    return "".join(result).strip()


def _release_tracks(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    media = payload.get("media") if isinstance(payload.get("media"), list) else []
    for disc_index, medium in enumerate(media, 1):
        if not isinstance(medium, Mapping):
            continue
        disc = int(medium.get("position") or disc_index)
        tracks = medium.get("tracks") if isinstance(medium.get("tracks"), list) else []
        for track_index, track in enumerate(tracks, 1):
            if not isinstance(track, Mapping):
                continue
            recording = track.get("recording") if isinstance(track.get("recording"), Mapping) else {}
            length = track.get("length") or recording.get("length")
            result.append(
                {
                    "disc_number": disc,
                    "track_number": int(track.get("position") or track_index),
                    "title": str(track.get("title") or recording.get("title") or ""),
                    "artist": _artist_credit(track.get("artist-credit")) or _artist_credit(recording.get("artist-credit")),
                    "recording_id": recording.get("id"),
                    "isrcs": recording.get("isrcs") if isinstance(recording.get("isrcs"), list) else [],
                    "duration_seconds": float(length) / 1000.0 if length else None,
                }
            )
    return result


def release_manifest(
    payload: Mapping[str, Any], preferred_format: str, *, confidence: float, reasons: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artist": _artist_credit(payload.get("artist-credit")),
        "release_id": str(payload.get("id") or ""),
        "recording_id": None,
        "album_edition": {
            "title": payload.get("title"),
            "date": payload.get("date"),
            "country": payload.get("country"),
            "status": payload.get("status"),
            "disambiguation": payload.get("disambiguation"),
            "barcode": payload.get("barcode"),
        },
        "expected_tracks": _release_tracks(payload),
        "preferred_audio": {
            "format": preferred_format,
            "quality": "lossless" if preferred_format == "FLAC" else "320 kbps",
        },
        "resolution": {"confidence": confidence, "reasons": list(reasons)},
        "musicbrainz_payload": payload,
    }


class SpotifyClient:
    """Small Client Credentials adapter used only for metadata resolution."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.metadata_http_timeout_seconds, follow_redirects=False)
        self._token: str | None = None

    def _access_token(self) -> str:
        if self._token:
            return self._token
        secret = self.settings.resolved_spotify_client_secret
        if not self.settings.spotify_client_id or not secret:
            raise WaitingForUser("Spotify API credentials are not configured; add them or attach a MusicBrainz link")
        response = self.client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(self.settings.spotify_client_id, secret),
        )
        if response.status_code != 200:
            raise RequestResolutionError(f"Spotify token request failed (HTTP {response.status_code})")
        self._token = str(response.json().get("access_token") or "")
        if not self._token:
            raise RequestResolutionError("Spotify token response did not contain an access token")
        return self._token

    def get(self, path: str) -> Mapping[str, Any]:
        return self.get_url(f"https://api.spotify.com/v1/{path.lstrip('/')}")

    def get_url(self, url: str) -> Mapping[str, Any]:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.spotify.com"
            or parsed.username
            or parsed.password
            or parsed.port
            or not parsed.path.startswith("/v1/")
        ):
            raise RequestResolutionError("Spotify pagination returned an unsafe API URL")
        response = self.client.get(
            url,
            headers={"Authorization": f"Bearer {self._access_token()}"},
        )
        if response.status_code != 200:
            raise RequestResolutionError(f"Spotify metadata request failed (HTTP {response.status_code})")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise RequestResolutionError("Spotify returned an unexpected response")
        return payload


def _score(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _recording_result(
    recording: Mapping[str, Any], mb: MusicBrainzClient, preferred: str, reason: str
) -> ResolutionResult:
    release_ids = list(
        dict.fromkeys(
            str(item.get("id"))
            for item in recording.get("releases", [])
            if isinstance(item, Mapping) and item.get("id")
        )
    )
    if not release_ids:
        reasons = (reason, "Recording has no attached release edition")
        manifest = {
            "schema_version": 1,
            "artist": _artist_credit(recording.get("artist-credit")),
            "release_id": None,
            "recording_id": recording.get("id"),
            "album_edition": None,
            "expected_tracks": [{
                "disc_number": 1,
                "track_number": 1,
                "title": recording.get("title"),
                "artist": _artist_credit(recording.get("artist-credit")),
                "recording_id": recording.get("id"),
                "isrcs": recording.get("isrcs") if isinstance(recording.get("isrcs"), list) else [],
                "duration_seconds": float(recording["length"]) / 1000.0 if recording.get("length") else None,
            }],
            "preferred_audio": {"format": preferred, "quality": "lossless" if preferred == "FLAC" else "320 kbps"},
            "resolution": {"confidence": 80.0, "reasons": list(reasons)},
        }
        return ResolutionResult(manifest, 80.0, reasons, True, "Choose an exact release edition")
    ambiguous = len(release_ids) > 1
    reasons = (reason,) + ((f"Recording appears on {len(release_ids)} editions",) if ambiguous else ())
    confidence = 88.0 if ambiguous else 98.0
    manifest = release_manifest(mb.lookup_release(release_ids[0]), preferred, confidence=confidence, reasons=reasons)
    manifest["recording_id"] = recording.get("id")
    return ResolutionResult(manifest, confidence, reasons, ambiguous, "Confirm the intended release edition" if ambiguous else None)


def resolve_reference(
    reference: RequestReference,
    settings: Settings,
    mb: MusicBrainzClient,
    *,
    preferred_format: PreferredFormat = PreferredFormat.FLAC,
    spotify: SpotifyClient | None = None,
) -> ResolutionResult:
    preferred = preferred_format.value
    if reference.source_type is AcquisitionSourceType.RELEASE:
        reasons = ("Exact MusicBrainz release link",)
        return ResolutionResult(release_manifest(mb.lookup_release(reference.identifier), preferred, confidence=100.0, reasons=reasons), 100.0, reasons)
    if reference.source_type is AcquisitionSourceType.RECORDING and reference.canonical_input.startswith("https://"):
        return _recording_result(mb.lookup_recording(reference.identifier), mb, preferred, "Exact MusicBrainz recording link")
    if reference.source_type is AcquisitionSourceType.ARTIST:
        rows = mb.search_artists(reference.artist or reference.identifier)
        confidence = _score(rows[0].get("score")) if rows else 0.0
        reasons = ("Artist requests require a release or recording selection",)
        manifest = {"schema_version": 1, "artist": rows[0].get("name") if rows else reference.artist, "artist_id": rows[0].get("id") if rows else None, "expected_tracks": [], "resolution": {"confidence": confidence, "reasons": list(reasons)}}
        return ResolutionResult(manifest, confidence, reasons, True, "Choose a specific song or album")

    matches: list[Any] = []
    if reference.canonical_input.startswith("https://open.spotify.com/"):
        spotify = spotify or SpotifyClient(settings)
        if reference.source_type is AcquisitionSourceType.PLAYLIST:
            children: list[RequestReference] = []
            page = spotify.get(f"playlists/{reference.identifier}/tracks?limit=100")
            seen_pages: set[str] = set()
            while True:
                for wrapper in page.get("items", []):
                    track = wrapper.get("track") if isinstance(wrapper, Mapping) else None
                    if not isinstance(track, Mapping) or not track.get("id"):
                        continue
                    artists = track.get("artists") if isinstance(track.get("artists"), list) else []
                    artist = ", ".join(str(row.get("name")) for row in artists if isinstance(row, Mapping) and row.get("name"))
                    children.append(RequestReference(AcquisitionSourceType.TRACK, f"https://open.spotify.com/track/{track['id']}", str(track["id"]), artist or None, str(track.get("name") or "")))
                next_url = page.get("next")
                if not isinstance(next_url, str) or not next_url:
                    break
                if next_url in seen_pages:
                    raise RequestResolutionError("Spotify playlist pagination repeated a page")
                seen_pages.add(next_url)
                page = spotify.get_url(next_url)
            manifest = {"schema_version": 1, "playlist_id": reference.identifier, "expected_tracks": [], "child_count": len(children), "resolution": {"confidence": 100.0, "reasons": ["Spotify playlist expanded into independent requests"]}}
            return ResolutionResult(manifest, 100.0, ("Playlist split into independent requests",), children=tuple(children))
        noun = "tracks" if reference.source_type is AcquisitionSourceType.TRACK else "albums"
        payload = spotify.get(f"{noun}/{reference.identifier}")
        artists = payload.get("artists") if isinstance(payload.get("artists"), list) else []
        artist = ", ".join(str(row.get("name")) for row in artists if isinstance(row, Mapping) and row.get("name"))
        if reference.source_type is AcquisitionSourceType.TRACK:
            external_ids = payload.get("external_ids") if isinstance(payload.get("external_ids"), Mapping) else {}
            isrc = external_ids.get("isrc")
            rows = mb.search_recording_by_isrc(str(isrc)) if isrc else mb.search_recordings(str(payload.get("name") or ""), artist=artist)
            if not rows:
                raise WaitingForUser("Spotify metadata resolved, but MusicBrainz had no matching recording")
            return _recording_result(mb.lookup_recording(str(rows[0].get("id"))), mb, preferred, "Spotify metadata matched to MusicBrainz")
        raw_tracks = payload.get("tracks", {}).get("items", []) if isinstance(payload.get("tracks"), Mapping) else []
        hints = AlbumHints(
            album=str(payload.get("name") or ""),
            album_artist=artist or None,
            tracks=tuple(TrackHint(title=str(row.get("name") or ""), duration_seconds=float(row["duration_ms"]) / 1000.0 if row.get("duration_ms") else None, track_number=row.get("track_number"), disc_number=row.get("disc_number")) for row in raw_tracks if isinstance(row, Mapping)),
            release_date=str(payload.get("release_date") or "") or None,
        )
        matches = mb.search_releases(hints)
    elif reference.source_type is AcquisitionSourceType.ALBUM:
        matches = mb.search_releases(AlbumHints(album=reference.title or reference.identifier, album_artist=reference.artist))
    else:
        rows = mb.search_recordings(reference.title or reference.identifier, artist=reference.artist)
        if not rows:
            raise WaitingForUser("No MusicBrainz recording matched this song request")
        top = rows[0]
        result = _recording_result(mb.lookup_recording(str(top.get("id"))), mb, preferred, "Text search matched a MusicBrainz recording")
        search_score = _score(top.get("score"))
        ambiguous = result.needs_user or search_score < settings.music_request_high_confidence_threshold
        reasons = result.reasons + (f"MusicBrainz search score {search_score:.1f}",)
        return ResolutionResult(result.manifest, min(search_score, result.confidence), reasons, ambiguous, "Confirm the recording and release edition" if ambiguous else None)

    if not matches:
        raise WaitingForUser("No MusicBrainz release matched this album request")
    top = matches[0]
    runner_up = matches[1].score if len(matches) > 1 else 0.0
    edition_text = f"{top.title} {top.disambiguation or ''}".casefold()
    risky = any(word in edition_text for word in _RISKY_EDITION_WORDS)
    ambiguous = top.score < settings.music_request_high_confidence_threshold or top.score - runner_up < settings.automatic_match_margin or risky
    reasons = [f"MusicBrainz release score {top.score:.1f}"]
    if risky:
        reasons.append("Edition wording requires review")
    return ResolutionResult(release_manifest(top.payload, preferred, confidence=top.score, reasons=reasons), top.score, tuple(reasons), ambiguous, "Confirm the exact release edition" if ambiguous else None)


def create_request_jobs(
    session: Any,
    references: Sequence[RequestReference],
    *,
    preferred_format: PreferredFormat,
    provider: AcquisitionProvider,
    parent_request_id: str | None = None,
) -> list[AcquisitionJob]:
    jobs: list[AcquisitionJob] = []
    for reference in references:
        request_id = str(uuid.uuid4())
        label = f"{reference.artist} — {reference.title}" if reference.artist and reference.title else reference.canonical_input
        job = AcquisitionJob(
            id=request_id,
            parent_request_id=parent_request_id,
            provider=provider.value,
            source_url=reference.canonical_input,
            source_type=reference.source_type.value,
            source_identifier=reference.identifier[:100],
            query_text=reference.canonical_input,
            display_title=label[:500],
            artist=reference.artist,
            album=reference.title if reference.source_type is AcquisitionSourceType.ALBUM else None,
            state=AcquisitionState.REQUESTED.value,
            preferred_format=preferred_format.value,
            acquisition_relative_directory=f"acquisitions/{request_id}",
        )
        session.add(job)
        add_acquisition_event(session, job, "Music request received")
        jobs.append(job)
    session.flush()
    return jobs


def resolve_next_request(
    database: Database,
    settings: Settings,
    *,
    mb_factory: Any | None = None,
    spotify: SpotifyClient | None = None,
) -> str | None:
    with database.session() as session:
        request_id = session.scalar(select(AcquisitionJob.id).where(AcquisitionJob.state == AcquisitionState.REQUESTED.value).order_by(AcquisitionJob.created_at).limit(1))
        if not request_id:
            return None
        claimed = session.execute(update(AcquisitionJob).where(AcquisitionJob.id == request_id, AcquisitionJob.state == AcquisitionState.REQUESTED.value).values(state=AcquisitionState.RESOLVING.value, resolution_attempts=AcquisitionJob.resolution_attempts + 1))
        if claimed.rowcount != 1:
            return None
        request = session.get(AcquisitionJob, request_id)
        assert request is not None
        add_acquisition_event(session, request, "Resolving request to MusicBrainz")
        query_text, source_type, artist, preferred = request.query_text or request.source_url, request.source_type, request.artist, PreferredFormat(request.preferred_format)

    try:
        reference = parse_request_reference(query_text, request_type=source_type, artist=artist)
        factory = mb_factory or (
            lambda: MusicBrainzClient(settings, cache=DatabaseJsonCache(database))
        )
        with factory() as mb:
            result = resolve_reference(
                reference, settings, mb, preferred_format=preferred, spotify=spotify
            )
    except WaitingForUser as exc:
        with database.session() as session:
            current = session.get(AcquisitionJob, request_id)
            if current:
                current.required_action = str(exc)
                transition_acquisition(session, current, AcquisitionState.WAITING_FOR_USER, str(exc), level="WARNING")
        return request_id
    except Exception as exc:
        with database.session() as session:
            current = session.get(AcquisitionJob, request_id)
            if current:
                current.error_code = exc.__class__.__name__.upper()[:100]
                current.error_message = str(exc)[:1000]
                transition_acquisition(session, current, AcquisitionState.FAILED, "Request resolution failed", level="ERROR")
        return request_id

    with database.session() as session:
        current = session.get(AcquisitionJob, request_id)
        if not current:
            return request_id
        current.manifest_json = json.dumps(result.manifest, ensure_ascii=False, separators=(",", ":"))
        current.confidence = result.confidence
        current.confidence_reasons_json = json.dumps(result.reasons, ensure_ascii=False)
        current.required_action = result.required_action
        if result.children:
            children = create_request_jobs(session, result.children, preferred_format=preferred, provider=AcquisitionProvider(current.provider), parent_request_id=current.id)
            for child in children:
                root = settings.acquisitions_dir / child.id
                (root / "incoming").mkdir(mode=0o750, parents=True, exist_ok=False)
                (root / "downloads").mkdir(mode=0o750, exist_ok=False)
                if settings.download_inbox_dir is not None:
                    (settings.download_inbox_dir / child.id).mkdir(mode=0o750, parents=True, exist_ok=True)
            transition_acquisition(session, current, AcquisitionState.COMPLETE, f"Playlist split into {len(result.children)} independent requests")
        elif result.needs_user:
            transition_acquisition(session, current, AcquisitionState.WAITING_FOR_USER, result.required_action or "Confirm the resolved metadata", level="WARNING")
        else:
            try:
                handoff = provider_adapter(current.provider).prepare(current, settings)
            except ProviderAdapterError as exc:
                current.error_code = "PROVIDER_CONFIGURATION"
                current.error_message = str(exc)
                transition_acquisition(session, current, AcquisitionState.FAILED, "Acquisition provider is not configured", level="ERROR")
            else:
                current.required_action = handoff.action if handoff.requires_user else None
                transition_acquisition(
                    session,
                    current,
                    AcquisitionState.WAITING_FOR_USER if handoff.requires_user else AcquisitionState.ACQUIRING,
                    "Manifest resolved; human acquisition is ready" if handoff.requires_user else "Manifest resolved; watching the request download directory",
                )
    return request_id
