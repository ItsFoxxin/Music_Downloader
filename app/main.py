from contextlib import asynccontextmanager
from pathlib import Path
import hmac
import hashlib
import os
import secrets
import shutil
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .db import Store
from .files import contained, linked, target
from .qbit import Qbit
from .worker import Worker


class ValidationRequest(BaseModel):
    source: str | None = Field(default=None, max_length=2000)
    torrent_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{40,64}$")


class ImportRequest(BaseModel):
    validation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    category: str = Field(pattern=r"^(Movies|TV)$")
    name: str = Field(min_length=1, max_length=500)


class ActionRequest(BaseModel):
    torrent_hash: str = Field(pattern=r"^[a-fA-F0-9]{40,64}$")
    action: str = Field(pattern=r"^(start|stop|recheck)$")


class AddRequest(BaseModel):
    magnet: str = Field(min_length=15, max_length=8192)
    category: str = Field(default="", max_length=100)


def create_app(settings=None, *, start_worker=True, qbit=None):
    s = settings or Settings()
    s.prepare()
    store = Store(s.config / "media.db")
    q = qbit or Qbit(s)
    worker = Worker(s, store, q)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        worker.close()

    app = FastAPI(title="Fox Den Media", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.worker, app.state.store = worker, store
    assets = Path(__file__).parent / "static"

    @app.middleware("http")
    async def security(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def auth(request: Request):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token and hmac.compare_digest(token.encode(), s.token.encode()):
            return
        cookie = request.cookies.get("foxden_session", "")
        try:
            issued, nonce, signature = cookie.split(".")
            valid_time = 0 <= time.time() - int(issued) < 8 * 3600
            expected = hmac.new(s.token.encode(), f"{issued}.{nonce}".encode(), hashlib.sha256).hexdigest()
            if valid_time and hmac.compare_digest(signature, expected):
                if request.method not in {"GET", "HEAD"} and request.headers.get("X-Foxden-Request") != "1":
                    raise HTTPException(403, "Missing same-origin request header.")
                return
        except (ValueError, TypeError):
            pass
        raise HTTPException(401, "Enter your APP_TOKEN to unlock Fox Den Media.")

    @app.post("/api/session", dependencies=[Depends(auth)])
    def login(request: Request):
        issued = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = hmac.new(s.token.encode(), f"{issued}.{nonce}".encode(), hashlib.sha256).hexdigest()
        response = JSONResponse({"authenticated": True})
        response.set_cookie("foxden_session", f"{issued}.{nonce}.{signature}", max_age=8*3600,
                            httponly=True, samesite="strict", secure=s.cookie_secure or request.url.scheme == "https", path="/")
        return response

    @app.get("/api/session", dependencies=[Depends(auth)])
    def session():
        return {"authenticated": True}

    @app.post("/api/logout", dependencies=[Depends(auth)])
    def logout():
        response = JSONResponse({"authenticated": False})
        response.delete_cookie("foxden_session", path="/")
        return response

    @app.get("/health")
    def health():
        alive = not start_worker or (worker.thread is not None and worker.thread.is_alive())
        return JSONResponse({"status": "ok" if alive else "worker unavailable"}, status_code=200 if alive else 503)

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        usage = shutil.disk_usage(s.media)
        return {"name": "Fox Den Media", "version": "0.1.0", "demo": s.demo,
                "qbit_configured": bool(s.qbit_url), "qbit_public_url": "" if s.demo else (s.qbit_public_url or s.qbit_url),
                "staging": str(s.staging), "media": str(s.media), "qbit_download_root": s.qbit_download_root,
                "free_bytes": usage.free, "total_bytes": usage.total, "full_decode": s.full_decode,
                "ffprobe_available": shutil.which(s.ffprobe) is not None, "ffmpeg_available": shutil.which(s.ffmpeg) is not None}

    @app.get("/api/torrents", dependencies=[Depends(auth)])
    def torrents():
        # Never expose trackers, cookies, or Web UI credentials to the frontend.
        keys = {"hash", "name", "progress", "state", "dlspeed", "upspeed", "eta", "size", "category", "ratio", "amount_left"}
        return [{k: v for k, v in t.items() if k in keys} for t in q.torrents()]

    @app.get("/api/staging", dependencies=[Depends(auth)])
    def staging():
        result = []
        for p in s.staging.iterdir():
            if p.name.startswith(".") or p.name.lower() in {"incomplete", "watch"}:
                continue
            result.append({"name": p.name, "path": p.name, "directory": p.is_dir(), "blocked": linked(p),
                           "size": p.stat().st_size if p.is_file() and not linked(p) else None})
            if len(result) >= 1000:
                break
        return result

    @app.get("/api/jobs", dependencies=[Depends(auth)])
    def jobs():
        rows = store.jobs()
        # Magnet URLs may contain private tracker tokens; keep them server-side.
        for row in rows:
            if row["kind"] == "add":
                row["payload"] = {"category": row["payload"].get("category", "")}
        return rows

    @app.get("/api/library", dependencies=[Depends(auth)])
    def library():
        return store.imports()

    @app.post("/api/validate", dependencies=[Depends(auth)], status_code=202)
    def queue_validation(body: ValidationRequest):
        if bool(body.source) == bool(body.torrent_hash):
            raise ValueError("Choose exactly one staging path or torrent.")
        if body.source:
            contained(s.staging, body.source)
        return store.enqueue("validate", body.model_dump(exclude_none=True))

    @app.post("/api/import", dependencies=[Depends(auth)], status_code=202)
    def queue_import(body: ImportRequest):
        destination = target(s, body.category, body.name)
        if os.path.lexists(destination):
            raise ValueError("Destination already exists; no files were changed.")
        review = store.job(body.validation_id)
        if not review or review["kind"] != "validate" or review["status"] != "succeeded":
            raise ValueError("Complete file validation before importing.")
        return store.enqueue("import", body.model_dump())

    @app.post("/api/library/{import_id}/audit", dependencies=[Depends(auth)], status_code=202)
    def queue_audit(import_id: str):
        if not any(r["id"] == import_id for r in store.imports()):
            raise HTTPException(404, "Import not found")
        return store.enqueue("audit", {"import_id": import_id})

    @app.post("/api/torrents/action", dependencies=[Depends(auth)], status_code=202)
    def torrent_action(body: ActionRequest):
        return store.enqueue("torrent_action", body.model_dump())

    @app.post("/api/torrents/add", dependencies=[Depends(auth)], status_code=202)
    def add_torrent(body: AddRequest):
        if not body.magnet.startswith("magnet:?") or "xt=urn:bt" not in body.magnet:
            raise ValueError("Provide a magnet link.")
        return store.enqueue("add", body.model_dump())

    return app
