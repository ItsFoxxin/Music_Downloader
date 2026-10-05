# Fox Den Media

One self-hosted Docker project for **music, movies, and TV**. The existing Fox Den
Music downloader lives alongside a new qBittorrent dashboard and a reviewed,
verified staging-to-library workflow. One gateway and one login connect both.

## What works in this development release

- Music dashboard, acquisition queue, human-controlled downloader browser,
  validation, MusicBrainz matching, imports, and library views from Fox Den Music 2.3.4.
- Movie/TV dashboard with qBittorrent progress, transfer rates, start/stop,
  recheck requests, magnet submission, and a link to the original Web UI.
- Read-only staging browser and durable SQLite jobs for validation and imports.
- FFprobe inspection, full audio/video decoding with FFmpeg (default), file
  stability/size checks, SHA-256 checksums, and explicit excluded-file reports.
- A review screen to choose `Movies/<folder>` or `TV/<show>/<season-or-batch>`.
- Verified copies published with an atomic **no-overwrite** directory rename.
  The original download remains available to qBittorrent for seeding.
- Import receipts, history, crash-recovery reconciliation, and library checksum
  audits to detect missing or changed imported files.
- An optional Compose extension bundles Gluetun/qBittorrent without giving
  qBittorrent an independent network or mounting the media library into it.

The qBittorrent Web UI remains a separate service. Its login is separate from
Fox Den's login. Opening the link is intentional; embedding is not required.

## Quick start on the Linux Docker host

1. Clone this repository and check out `dev`. Copy `.env.example` to `.env`.
2. Set `PUID` and `PGID` to the intended **non-root** account/group. Set `APP_TOKEN`
   to a random secret of at least 24 characters and `CSRF_SECRET` to another random
   secret. For example: `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
3. Configure your existing music paths and these movie/TV values:

   ```dotenv
   QBIT_URL=http://your-nas-address:8080
   QBIT_PUBLIC_URL=http://your-nas-address:8080
   QBIT_USERNAME=admin
   QBIT_PASSWORD=your-private-web-ui-password
   QBIT_DOWNLOAD_ROOT=/downloads
   TORRENT_STAGING_PATH=/absolute/host/path/to/torrent-downloads
   MEDIA_PATH=/absolute/host/path/to/media
   MEDIA_CONFIG_PATH=/absolute/host/path/to/foxden-media-config
   ```

4. Pre-create every bind-mounted directory listed in `.env`. Give the service
   UID/group read access to torrent staging and write access to its own config,
   music staging/inbox, browser config, and media destinations. Keep both SQLite
   config directories on a local filesystem. **Do not recursively change existing
   library ownership.** Check its existing group/ACL model first.
5. Keep `WEB_BIND_IP=127.0.0.1` behind your existing HTTPS reverse proxy, or set a
   specific LAN IP for LAN access. Set `COOKIE_SECURE=true` when using HTTPS.
   Start the app:

   ```sh
   docker compose -f compose.yaml config --quiet
   docker compose -f compose.yaml up -d --build
   docker compose -f compose.yaml ps
   docker compose -f compose.yaml logs --tail=100 media web worker gateway
   ```

6. Open `http://your-server:8000/transfers/` and enter `APP_TOKEN`. Sessions last
   eight hours. Music is at `/`; movies and TV are at `/transfers/`. The gateway
   requires the same session for music and the music downloader browser.

For an existing music deployment, stop it and back up its complete config
directory before reusing its paths. Preserve the original `.env`; merge settings
into the new project instead of overwriting it. The bundled music component has
its own schema upgrade instructions in [music/README.md](music/README.md).

## Staging-to-library workflow

1. Download through qBittorrent. Use its Web UI or submit a magnet in Fox Den.
2. In **Downloads**, choose **Validate** on a completed torrent. Fox Den verifies
   selected-file completion and maps qBittorrent's save path to its read-only mount.
   **Recheck** requests a qBittorrent hash recheck; wait for qBittorrent to finish
   before validating. A successful API request is not proof of recheck completion.
3. Review the file list, excluded files, validation method, and destination.
4. Approve the import. Fox Den copies into a hidden directory on the media drive,
   verifies each copied SHA-256, and publishes the complete directory in one rename.
5. Use **Verify library** later to compare imported files to their recorded checksums.

You can also validate files directly from **Staging & review**. This checks stable
files and readable media, but does **not** prove a corresponding torrent is complete.
Archives and executable files are excluded and never executed or extracted.

Folder selection is manual in this release. Existing destination directories are
never merged or overwritten. For additional TV episodes, select a new episode/batch
subfolder (for example `Show Name/Season 01/Episodes 03-04`) or import a complete
season to a new season folder. Full movie/TV identity matching, automatic renaming,
and series-aware incremental imports are tracked in [next-steps.md](next-steps.md).

## Connections and boundaries

- All deployment addresses, paths, credentials, and VPN peer settings are in `.env`
  or the private key file. `.env`, runtime data, secrets, and caches are ignored.
- The movie/TV service is non-root, with a read-only container filesystem,
  dropped capabilities, and no Docker socket. Staging is mounted read-only.
- The browser receives a signed, HttpOnly, SameSite session cookie, not qBittorrent
  credentials. API writes also require a same-origin custom header. The music
  component retains its existing CSRF protections. Use HTTPS for remote access.
- qBittorrent is accessed through its official API with a reusable login cookie;
  failed authentication retries are limited to once per minute.
- File validation is integrity/readability checking, **not** malware scanning,
  title identification, or proof of content provenance. A full decode can take a
  long time. `FULL_DECODE=false` is explicitly reported as metadata inspection only.
- Imports copy data because staging and media may be different filesystems. This
  needs free space for the entire import and preserves seeding. No hardlinks,
  destructive cleanup, torrent deletion, source moves, or automatic movie/TV imports.
- One media process/worker is supported. Do not scale it to multiple replicas.
- The movie/TV library view covers Fox Den imports, not an inventory of all
  pre-existing media. Imported files can be audited without contacting qBittorrent.

See [architecture](docs/architecture.md), [VPN integration](docs/torrent-vpn.md),
[recovery](docs/recovery.md), and [validation evidence](docs/validation.md).

## Development

Python 3.12+, FFmpeg, and FFprobe are required. Commands from the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python scripts/demo.py
```

The local demo binds only to `127.0.0.1`, prints a temporary access token, generates
short sample movies, and uses a fake qBittorrent adapter. It never downloads a torrent
or contacts a NAS. Set `FFMPEG_PATH` / `FFPROBE_PATH` if the tools are outside PATH.
The demo runs only the movie/TV service; use Docker for the shared music gateway.

The copied music tests can be run independently:

```sh
python -m pip install -r music/backend/requirements-dev.txt
PYTHONPATH=music/backend/src python -m pytest -c music/backend/pyproject.toml music/backend/tests -q
```
