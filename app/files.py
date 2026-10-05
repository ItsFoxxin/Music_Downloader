import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import time
import uuid

MEDIA = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".ts", ".m2ts", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma", ".aiff"}
SIDECARS = {".srt", ".ass", ".ssa", ".vtt", ".nfo", ".jpg", ".jpeg", ".png"}
DEMUXERS = "mov,matroska,webm,avi,mpegts,mp3,flac,aac,wav,ogg,aiff,asf"


def relative_parts(value):
    value = str(value)
    if not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("Use a relative path with forward slashes.")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in {"", ".", ".."} for x in value.split("/")):
        raise ValueError("Absolute paths and traversal are not allowed.")
    for part in p.parts:
        if part.endswith((" ", ".")) or any(ord(c) < 32 or c in '<>"|?*' for c in part):
            raise ValueError("Path contains unsupported characters.")
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("Reserved filename is not allowed.")
    return p.parts


def linked(path):
    st = path.lstat()
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def contained(root, relative, *, existing=True):
    parts = relative_parts(relative)
    current = root
    if linked(root):
        raise ValueError("Root may not be a symlink or junction.")
    for part in parts:
        current = current / part
        if os.path.lexists(current) and linked(current):
            raise ValueError("Symlinks and junctions are not allowed.")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes its configured root.")
    if existing and not current.exists():
        raise ValueError("File or directory is missing: " + relative)
    return current


def signature(path):
    st = path.stat()
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("Only regular files are accepted.")
    if st.st_size == 0:
        raise ValueError("Empty file: " + path.name)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "inode": st.st_ino}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(settings, source):
    path = contained(settings.staging, source)
    if path.is_file():
        return [{"path": source, "size": path.stat().st_size}]
    result = []
    visited = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        visited += len(dirs) + len(files)
        if visited > settings.max_files:
            raise ValueError("Too many entries; select a smaller staging folder.")
        for name in dirs + files:
            full = Path(base) / name
            if linked(full):
                raise ValueError("Symlink or junction found in staging.")
        for name in files:
            full = Path(base) / name
            result.append({"path": full.relative_to(settings.staging).as_posix(), "size": full.stat().st_size})
    return result


def probe(path, settings):
    try:
        proc = subprocess.run([settings.ffprobe, "-v", "error", "-protocol_whitelist", "file", "-format_whitelist", DEMUXERS, "-show_format", "-show_streams", "-of", "json", str(path)],
                              capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise ValueError("ffprobe is required. Install FFmpeg or set FFPROBE_PATH.") from None
    if proc.returncode:
        raise ValueError("Media inspection failed: " + proc.stderr[-500:])
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    playable = [s for s in streams if s.get("codec_type") in {"audio", "video"} and not s.get("disposition", {}).get("attached_pic")]
    if not playable or float(info.get("format", {}).get("duration", 0)) <= 0:
        raise ValueError("No playable audio/video stream or valid duration.")
    if settings.full_decode:
        try:
            # Capture only a bounded tail on disk; full decoding can run for hours.
            with __import__("tempfile").TemporaryFile() as log:
                proc = subprocess.run([settings.ffmpeg, "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file", "-format_whitelist", DEMUXERS, "-i", str(path),
                                       "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"],
                                      stdout=subprocess.DEVNULL, stderr=log, timeout=settings.decode_timeout)
                if proc.returncode:
                    log.seek(max(0, log.tell() - 500))
                    raise ValueError("Full media decode failed: " + log.read().decode("utf-8", "replace"))
        except FileNotFoundError:
            raise ValueError("ffmpeg is required for full decode. Install FFmpeg or set FFMPEG_PATH.") from None
    return {"duration": float(info["format"]["duration"]),
            "codecs": sorted({s.get("codec_name", "unknown") for s in playable}),
            "video": any(s.get("codec_type") == "video" for s in playable),
            "audio": any(s.get("codec_type") == "audio" for s in playable),
            "validation": "full decode" if settings.full_decode else "metadata inspection only"}


def validate(settings, qbit, payload):
    entries = qbit.manifest(payload["torrent_hash"]) if payload.get("torrent_hash") else inventory(settings, payload["source"])
    if len(entries) > settings.max_files:
        raise ValueError("Too many files in one import.")
    selected, skipped = [], []
    seen = set()
    for entry in entries:
        path = contained(settings.staging, entry["path"])
        if path.suffix.lower() not in MEDIA | SIDECARS:
            skipped.append(entry["path"])
            continue
        sig = signature(path)
        if sig["size"] != entry["size"]:
            raise ValueError("File size differs from the torrent manifest: " + entry["path"])
        folded = entry["path"].casefold()
        if folded in seen:
            raise ValueError("Duplicate or case-conflicting file names.")
        seen.add(folded)
        selected.append({"path": entry["path"], "snapshot": sig})
    if not any(Path(f["path"]).suffix.lower() in MEDIA for f in selected):
        raise ValueError("No supported media files. Archives must be extracted outside this application.")
    common = os.path.commonpath([str(Path(f["path"]).parent) for f in selected])
    time.sleep(settings.settle_seconds)
    for entry in selected:
        path = contained(settings.staging, entry["path"])
        if signature(path) != entry["snapshot"]:
            raise ValueError("File is still changing: " + entry["path"])
        entry["sha256"] = digest(path)
        entry["output"] = Path(entry["path"]).relative_to(common).as_posix()
        entry["media"] = probe(path, settings) if path.suffix.lower() in MEDIA else None
        if signature(path) != entry["snapshot"]:
            raise ValueError("File changed during validation: " + entry["path"])
    warnings = []
    if not payload.get("torrent_hash"):
        warnings.append("Untracked staging files: torrent completeness has not been checked.")
    if not settings.full_decode:
        warnings.append("Full decode is disabled; metadata inspection cannot establish full playback integrity.")
    if skipped:
        warnings.append("Unsupported files were excluded. Review the skipped list before importing.")
    return {"files": selected, "skipped": skipped, "warnings": warnings,
            "source": payload, "bytes": sum(e["snapshot"]["size"] for e in selected),
            "torrent_check": "qBittorrent reports selected files complete; recheck is a separate action" if payload.get("torrent_hash") else "not linked to a torrent",
            "validated_at": time.time()}


def rename_no_replace(source, destination):
    if sys.platform == "win32":
        os.rename(source, destination)  # Windows refuses an existing target.
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        fn = getattr(libc, "renameat2", None)
        if fn is None:
            raise ValueError("Atomic no-overwrite rename is unavailable on this system.")
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        if fn(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(destination))
    else:
        raise ValueError("Atomic imports currently support Linux and Windows.")


def target(settings, category, name):
    if category not in {"Movies", "TV", "Music"}:
        raise ValueError("Choose Movies, TV, or Music.")
    relative_parts(name)
    return contained(settings.media, category + "/" + name, existing=False)


def import_files(settings, store, qbit, payload, job_id):
    review = store.job(payload["validation_id"])
    if not review or review["kind"] != "validate" or review["status"] != "succeeded":
        raise ValueError("A successful validation is required before import.")
    report = review["result"]
    destination = target(settings, payload["category"], payload["name"])
    relative_destination = destination.relative_to(settings.media).as_posix()
    if os.path.lexists(destination):
        raise ValueError("Destination already exists. Choose a new folder; nothing was overwritten.")
    if report["source"].get("torrent_hash"):
        current = qbit.manifest(report["source"]["torrent_hash"])
        current_files = {f["path"]: f["size"] for f in current}
        if any(current_files.get(f["path"]) != f["snapshot"]["size"] for f in report["files"]):
            raise ValueError("Torrent files changed. Validate again.")
    for f in report["files"]:
        if f["media"] and payload["category"] in {"Movies", "TV"} and not f["media"]["video"]:
            raise ValueError("An audio-only file is selected for a video library. Choose Music or a narrower staging source.")
    # Disk use includes a full isolated copy, preserving qBittorrent seeding sources.
    if shutil.disk_usage(settings.media).free < report["bytes"] + 64 * 1024 * 1024:
        raise ValueError("Insufficient media disk space for a verified copy.")
    imports_dir = contained(settings.media, ".imports", existing=False)
    imports_dir.mkdir(exist_ok=True)
    temporary = imports_dir / job_id
    temporary.mkdir(exist_ok=False)
    manifest = {"id": job_id, "destination": relative_destination, "files": [], "source": report["source"], "created": time.time()}
    published = False
    try:
        for entry in report["files"]:
            source = contained(settings.staging, entry["path"])
            if signature(source) != entry["snapshot"]:
                raise ValueError("Source changed since validation. Validate again: " + entry["path"])
            copied = contained(temporary, entry["output"], existing=False)
            copied.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as src, copied.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if signature(source) != entry["snapshot"] or digest(copied) != entry["sha256"]:
                raise ValueError("Source changed or copy verification failed: " + entry["path"])
            manifest["files"].append({"path": entry["output"], "size": entry["snapshot"]["size"], "sha256": entry["sha256"], "media": entry["media"]})
        receipt = temporary / ".foxden-receipt.json"
        with receipt.open("x", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Validate every component again before publishing. Destination parents are owned by the operator.
        destination = target(settings, payload["category"], payload["name"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        rename_no_replace(temporary, destination)
        published = True
        store.record_import(job_id, relative_destination, manifest)
        return {"destination": relative_destination, "files": len(manifest["files"]), "bytes": report["bytes"], "source_preserved": True}
    except Exception:
        # Only our unique, unpublished temporary directory is removed.
        if not published and temporary.exists() and temporary.parent.resolve() == imports_dir.resolve():
            shutil.rmtree(temporary)
        raise


def audit(settings, store, import_id):
    record = next((r for r in store.imports() if r["id"] == import_id), None)
    if not record:
        raise ValueError("Import record not found.")
    issues = []
    for f in record["manifest"]["files"]:
        try:
            path = contained(settings.media, record["destination"] + "/" + f["path"])
            if signature(path)["size"] != f["size"] or digest(path) != f["sha256"]:
                issues.append({"path": f["path"], "issue": "File differs from its validated import checksum."})
        except (ValueError, OSError) as e:
            issues.append({"path": f["path"], "issue": str(e)})
    store.health(import_id, "issues found" if issues else "verified")
    return {"destination": record["destination"], "issues": issues, "checked_files": len(record["manifest"]["files"])}
