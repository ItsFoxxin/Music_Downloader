from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import httpx

from .config import Settings


class FingerprintError(RuntimeError):
    pass


def fingerprint_audio(path: Path, settings: Settings) -> dict[str, Any]:
    """Run fpcalc without a shell and optionally ask AcoustID for recording IDs."""

    try:
        completed = subprocess.run(
            [settings.fpcalc_path, "-json", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.ffprobe_timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FingerprintError("Chromaprint fpcalc could not inspect an acquired file") from exc
    try:
        payload = json.loads(completed.stdout)
        fingerprint = str(payload["fingerprint"])
        duration = int(round(float(payload["duration"])))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise FingerprintError("fpcalc returned an invalid fingerprint response") from exc
    evidence: dict[str, Any] = {
        "duration": duration,
        "fingerprint_length": len(fingerprint),
        "acoustid_recording_ids": [],
        "mode": "local_only",
    }
    if not settings.acoustid_api_key:
        return evidence
    try:
        response = httpx.get(
            settings.acoustid_base_url,
            params={
                "client": settings.acoustid_api_key,
                "duration": str(duration),
                "fingerprint": fingerprint,
                "meta": "recordings",
                "format": "json",
            },
            timeout=settings.metadata_http_timeout_seconds,
            follow_redirects=False,
        )
    except httpx.TransportError as exc:
        raise FingerprintError("AcoustID lookup could not connect") from exc
    if response.status_code != 200:
        raise FingerprintError(f"AcoustID lookup failed (HTTP {response.status_code})")
    try:
        remote = response.json()
    except ValueError as exc:
        raise FingerprintError("AcoustID returned invalid JSON") from exc
    recording_ids: list[str] = []
    for result in remote.get("results", []) if isinstance(remote, Mapping) else []:
        if not isinstance(result, Mapping):
            continue
        for recording in result.get("recordings", []):
            if isinstance(recording, Mapping) and recording.get("id"):
                recording_ids.append(str(recording["id"]))
    evidence["mode"] = "acoustid"
    evidence["acoustid_recording_ids"] = list(dict.fromkeys(recording_ids))
    return evidence
