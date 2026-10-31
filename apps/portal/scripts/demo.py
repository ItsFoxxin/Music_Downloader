"""Run the Portal against two in-process mock module adapters."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from foxden_portal.app import create_app
from foxden_portal.config import Settings
from foxden_portal.modules import ModuleClient


def handler(request: httpx.Request) -> httpx.Response:
    module = "music" if request.url.host == "music.mock" else "media"
    healthy = module == "music"
    return httpx.Response(200, json={
        "contract_version": "1.0", "module_id": module,
        "module_name": "Music" if module == "music" else "Movies & TV",
        "module_version": "mock-1.0",
        "health": {"status": "healthy" if healthy else "unhealthy",
                   "summary": "Ready" if healthy else "Mock scanner needs attention"},
        "capabilities": [{"id": "library", "label": "Library", "enabled": True}],
        "activity": [{
            "id": f"{module}-demo-1", "kind": "import" if healthy else "review",
            "title": "Imported mock album" if healthy else "Mock item needs review",
            "status": "complete" if healthy else "needs-review",
            "occurred_at": "2026-10-27T16:00:00Z",
            "path": "/history",
        }],
    })


if __name__ == "__main__":
    directory = Path(tempfile.mkdtemp(prefix="foxden-portal-demo-"))
    os.environ.setdefault("PORTAL_DATABASE_PATH", str(directory / "portal.db"))
    os.environ.setdefault("PORTAL_PUBLIC_URL", "http://127.0.0.1:8020")
    os.environ.setdefault("PORTAL_COOKIE_SECURE", "false")
    os.environ.setdefault("PORTAL_MODULES_JSON", '[{"id":"music","name":"Music","base_url":"http://music.mock","navigation_path":"/music/"},{"id":"media","name":"Movies & TV","base_url":"http://media.mock","navigation_path":"/media/"}]')
    settings = Settings.from_env()
    app = create_app(settings, ModuleClient(settings.module_timeout_seconds, httpx.MockTransport(handler)))
    uvicorn.run(app, host="127.0.0.1", port=8020)
