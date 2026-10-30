"""Presentation-safe Movies/TV status for the Fox Den Portal contract."""
from __future__ import annotations

from datetime import datetime, timezone


CONTRACT_VERSION = "1.0"


def module_summary(*, version: str, worker_available: bool,
                   qbit_enabled: bool, browser_enabled: bool) -> dict:
    """Build contract v1 without reading application records or configuration."""
    return {
        "contract_version": CONTRACT_VERSION,
        "module_id": "media",
        "module_name": "Movies & TV",
        "module_version": version,
        "health": {
            "status": "healthy" if worker_available else "unhealthy",
            "summary": "Movies & TV is ready." if worker_available else "Movies & TV worker is unavailable.",
        },
        "capabilities": [
            {"id": "media.requests", "label": "Requests", "enabled": True},
            {"id": "media.library", "label": "Library", "enabled": True},
            {"id": "media.acquisition", "label": "Downloads", "enabled": qbit_enabled},
            {"id": "media.browser", "label": "Guided browser", "enabled": browser_enabled},
        ],
        # Activity is available only through the separately authenticated endpoint.
        "activity": [],
    }


def sanitized_activity(rows: list[dict]) -> dict:
    """Expose bounded state changes without names, sources, filesystem paths, or tokens."""
    activity = []
    for row in rows[:20]:
        occurred = row.get("updated") or row.get("created")
        if not occurred:
            continue
        occurred_at = datetime.fromtimestamp(float(occurred), timezone.utc).isoformat().replace("+00:00", "Z")
        activity.append({
            "id": str(row.get("id", "event"))[:100],
            "kind": "media.request",
            "title": "Media request updated",
            "status": str(row.get("status", "unknown"))[:60],
            "occurred_at": occurred_at,
            "path": "/media/?view=requests",
        })
    return {"contract_version": CONTRACT_VERSION, "module_id": "media", "activity": activity}
