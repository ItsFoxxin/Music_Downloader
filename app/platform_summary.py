"""Presentation-safe Movies/TV status for the Fox Den Portal contract."""
from __future__ import annotations


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
        # Activity remains empty until trusted Portal-to-module authentication is wired.
        "activity": [],
    }
