from contextlib import asynccontextmanager
from pathlib import Path
import base64
import html
import hmac
import hashlib
import os
import secrets
import shutil
import time
from urllib.parse import parse_qs, unquote_plus, urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from foxden_identity import IdentityError, ReplayGuard, TrustedKeySet

from .config import Settings
from .db import Store
from .files import contained, linked, target
from .platform_summary import module_summary, sanitized_activity
from .qbit import Qbit
from .worker import Worker
from .version import __version__


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


class MediaRequestCreate(BaseModel):
    query: str = Field(min_length=1, max_length=8192)
    media_type: str = Field(pattern=r"^(Movie|TV)$")
    title: str | None = Field(default=None, max_length=500)


class MediaRequestAttach(BaseModel):
    torrent_hash: str = Field(pattern=r"^[a-fA-F0-9]{40,64}$")


def request_details(query, title=None):
    value = query.strip()
    torrent_hash = None
    if value.startswith("magnet:?"):
        params = parse_qs(urlsplit(value).query)
        xt = next((x for x in params.get("xt", []) if x.lower().startswith("urn:btih:")), "")
        torrent_hash = xt.rsplit(":", 1)[-1].lower()
        if len(torrent_hash) == 32:
            try:
                torrent_hash = base64.b32decode(torrent_hash.upper()).hex()
            except ValueError:
                torrent_hash = ""
        if not torrent_hash or len(torrent_hash) not in {40, 64} or any(c not in "0123456789abcdef" for c in torrent_hash):
            raise ValueError("Magnet must contain a valid BitTorrent info hash.")
        inferred = unquote_plus(params.get("dn", [""])[0]).strip()
    else:
        parsed = urlsplit(value)
        if parsed.scheme and (parsed.scheme not in {"http", "https"} or not parsed.hostname):
            raise ValueError("Use a title, an HTTP(S) IMDb/TMDB link, or a magnet link.")
        if parsed.scheme:
            value = parsed._replace(query="", fragment="").geturl()
            inferred = unquote_plus(parsed.path.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").strip()
        else:
            inferred = value
    display = (title or inferred or "Untitled request").strip()
    if not display or len(display) > 500:
        raise ValueError("Provide a destination title of 1 to 500 characters.")
    return value, display, torrent_hash


def create_app(settings=None, *, start_worker=True, qbit=None):
    s = settings or Settings()
    s.prepare()
    store = Store(s.config / "media.db")
    q = qbit or Qbit(s)
    worker = Worker(s, store, q)
    trusted_identities = (TrustedKeySet.from_file(s.identity_public_keys_file)
                          if s.identity_public_keys_file else None)
    user_replay = ReplayGuard()
    service_replay = ReplayGuard()

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        worker.close()

    app = FastAPI(title="Fox Den Media", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
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
        assertion = request.headers.get("X-FoxDen-Identity", "")
        if assertion:
            if not trusted_identities:
                raise HTTPException(401, "Authentication required.")
            try:
                identity = trusted_identities.verify(
                    assertion, issuer=s.identity_issuer, audience="media", token_use="user",
                    required_scopes={"module:access"}, replay_guard=user_replay,
                )
                if not identity["roles"] or not set(identity["roles"]).issubset({"user", "admin"}):
                    raise IdentityError("Identity role is invalid.")
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    if request.headers.get("Origin", "").rstrip("/") != s.public_origin:
                        raise HTTPException(403, "Request origin validation failed.")
                return identity
            except IdentityError:
                raise HTTPException(401, "Authentication required.") from None
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token and hmac.compare_digest(token.encode(), s.token.encode()):
            return {"roles": ["admin"], "token_use": "legacy"}
        cookie = request.cookies.get("foxden_session", "")
        try:
            issued, nonce, signature = cookie.split(".")
            valid_time = 0 <= time.time() - int(issued) < 8 * 3600
            expected = hmac.new(s.token.encode(), f"{issued}.{nonce}".encode(), hashlib.sha256).hexdigest()
            if valid_time and hmac.compare_digest(signature, expected):
                if request.method not in {"GET", "HEAD"} and request.headers.get("X-Foxden-Request") != "1":
                    raise HTTPException(403, "Missing same-origin request header.")
                return {"roles": ["admin"], "token_use": "legacy"}
        except (ValueError, TypeError):
            pass
        raise HTTPException(401, "Enter your APP_TOKEN to unlock Fox Den Media.")

    def admin_auth(identity=Depends(auth)):
        if "admin" not in identity.get("roles", []):
            raise HTTPException(403, "Administrator permission required.")
        return identity

    def service_auth(request: Request):
        assertion = request.headers.get("X-FoxDen-Identity", "")
        if not assertion or not trusted_identities:
            raise HTTPException(401, "Service authentication required.")
        try:
            identity = trusted_identities.verify(
                assertion, issuer=s.identity_issuer, audience="media", token_use="service",
                required_scopes={"activity:read"}, replay_guard=service_replay,
            )
            if identity["roles"]:
                raise IdentityError("Service roles are invalid.")
            return identity
        except IdentityError:
            raise HTTPException(401, "Service authentication required.") from None

    @app.post("/api/session")
    def login(request: Request, identity=Depends(auth)):
        if identity.get("token_use") == "user":
            # Portal-authenticated requests receive a fresh assertion at ingress;
            # never translate a restricted identity into the legacy admin cookie.
            return {"authenticated": True}
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

    @app.get("/api/platform/v1/summary")
    def platform_summary():
        alive = not start_worker or (worker.thread is not None and worker.thread.is_alive())
        return module_summary(version=__version__, worker_available=alive,
                              qbit_enabled=bool(s.qbit_url), browser_enabled=bool(s.media_browser_home_url))

    @app.get("/api/platform/v1/activity", dependencies=[Depends(service_auth)])
    def platform_activity():
        return sanitized_activity(store.media_requests())

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/request-browser/{request_id}", dependencies=[Depends(auth)], response_class=HTMLResponse)
    def request_browser(request_id: str):
        media_request = store.media_request(request_id)
        if not media_request:
            raise HTTPException(404, "Request not found")
        title = html.escape(media_request["title"], quote=True)
        media_type = html.escape(media_request["media_type"], quote=True)
        home = html.escape(s.media_browser_home_url, quote=True)
        qbit_link = ""
        if s.qbit_public_url and not s.demo:
            public_url = html.escape(s.qbit_public_url, quote=True)
            qbit_link = (f'<a class="browser-button" href="{public_url}" target="_blank" '
                         'rel="noopener noreferrer">Open qBittorrent ↗</a>')
        return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title} · Fox Den request browser</title>
<link rel="stylesheet" href="../assets/request-browser.css">
<script src="../assets/request-browser.js" defer></script></head>
<body data-home-url="{home}"><header class="browser-toolbar">
<a class="browser-button primary" href="../?view=requests">← Back to requests</a>
<button class="browser-button" type="button" data-browser-home
 data-bridge-url="../assets/request-browser-bridge.js" disabled>Media discovery home</button>
<button class="browser-button" type="button" data-copy-request>Copy request</button>
{qbit_link}<input id="browser-request" type="text" value="{title}" readonly
 aria-label="{media_type} request"></header>
<div class="browser-help"><b>{media_type} request:</b> {title}. Search in the visible browser,
complete any login or CAPTCHA yourself, add your chosen result to qBittorrent, then return and attach it.
<span data-browser-feedback role="status" aria-live="polite"></span></div>
<iframe class="browser-frame" src="/server-browser/" data-home-url="{home}"
 title="Contained media browser" referrerpolicy="no-referrer"
 allow="fullscreen; clipboard-read; clipboard-write" allowfullscreen></iframe></body></html>""")

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        usage = shutil.disk_usage(s.media)
        return {"name": "Fox Den Media", "version": __version__, "demo": s.demo,
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

    @app.get("/api/requests", dependencies=[Depends(auth)])
    def media_requests():
        return store.media_requests()

    @app.get("/api/requests/{request_id}", dependencies=[Depends(auth)])
    def media_request(request_id: str):
        result = store.media_request(request_id)
        if not result:
            raise HTTPException(404, "Request not found")
        return result

    @app.post("/api/requests", dependencies=[Depends(admin_auth)], status_code=202)
    def create_media_request(body: MediaRequestCreate):
        query, title, torrent_hash = request_details(body.query, body.title)
        acquisition_id = None
        if torrent_hash:
            acquisition_id = store.enqueue("add", {"magnet": query, "category": body.media_type.lower()})["id"]
        public_query = "Magnet link" if torrent_hash else query
        return store.create_request(body.media_type, public_query, title, torrent_hash, acquisition_id)

    @app.post("/api/requests/{request_id}/attach", dependencies=[Depends(admin_auth)], status_code=202)
    def attach_media_request(request_id: str, body: MediaRequestAttach):
        request = store.media_request(request_id)
        if not request:
            raise HTTPException(404, "Request not found")
        if request["status"] not in {"waiting_for_user", "failed"}:
            raise ValueError("This request already has an active torrent.")
        return store.update_request(request_id, torrent_hash=body.torrent_hash.lower(),
                                    status="acquiring", validation_id=None,
                                    import_id=None, error=None)

    @app.post("/api/validate", dependencies=[Depends(admin_auth)], status_code=202)
    def queue_validation(body: ValidationRequest):
        if bool(body.source) == bool(body.torrent_hash):
            raise ValueError("Choose exactly one staging path or torrent.")
        if body.source:
            contained(s.staging, body.source)
        return store.enqueue("validate", body.model_dump(exclude_none=True))

    @app.post("/api/import", dependencies=[Depends(admin_auth)], status_code=202)
    def queue_import(body: ImportRequest):
        destination = target(s, body.category, body.name)
        if os.path.lexists(destination):
            raise ValueError("Destination already exists; no files were changed.")
        review = store.job(body.validation_id)
        if not review or review["kind"] != "validate" or review["status"] != "succeeded":
            raise ValueError("Complete file validation before importing.")
        job = store.enqueue("import", body.model_dump())
        request = store.request_for_validation(body.validation_id)
        if request:
            store.update_request(request["id"], status="importing", import_id=job["id"], error=None)
        return job

    @app.post("/api/library/{import_id}/audit", dependencies=[Depends(admin_auth)], status_code=202)
    def queue_audit(import_id: str):
        if not any(r["id"] == import_id for r in store.imports()):
            raise HTTPException(404, "Import not found")
        return store.enqueue("audit", {"import_id": import_id})

    @app.post("/api/torrents/action", dependencies=[Depends(admin_auth)], status_code=202)
    def torrent_action(body: ActionRequest):
        return store.enqueue("torrent_action", body.model_dump())

    @app.post("/api/torrents/add", dependencies=[Depends(admin_auth)], status_code=202)
    def add_torrent(body: AddRequest):
        if not body.magnet.startswith("magnet:?") or "xt=urn:bt" not in body.magnet:
            raise ValueError("Provide a magnet link.")
        return store.enqueue("add", body.model_dump())

    return app
