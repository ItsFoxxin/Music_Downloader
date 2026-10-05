# Validation evidence

Local verification on 2026-10-05, Windows, Python 3.12:

| Check | Result |
| --- | --- |
| New movie/TV tests | **33 passed, 1 skipped** |
| Bundled music regression tests | **214 passed, 2 skipped** |
| JavaScript parser (`node --check`) | Passed |
| App-only Docker Compose configuration | Passed |
| App + VPN extension Compose configuration | Passed |
| Real local Nginx configuration check | Passed with localhost upstream/Windows log-path substitutions |
| Nginx shared-session HTTP test | Anonymous redirect, authenticated music, media API, static routing, logout passed |
| Browser walkthrough | Login, validation report, approved import, library record, checksum audit, music/movie navigation passed |
| Browser console | No warning/error entries observed during the walkthrough |
| Mobile breakpoint | 390px viewport inspected; no document-wide horizontal overflow |

Tests used FFmpeg/FFprobe 9.0.2 with generated short audio/video fixtures. Workflow
tests exercised full decoding, Unicode paths, unchanged source preservation,
SHA-256 copy verification, copy failure cleanup, existing-destination refusal,
post-validation source changes, corrupt media, unsafe paths, excluded executables
and archives, incomplete torrent rejection, qBittorrent path mapping, cookie
reuse/auth retry limits, signed sessions, CSRF header checks, and restart receipts.

Three symlink creation tests were skipped because the Windows account lacked that
privilege. A Linux CI workflow is included so those tests can run where supported.

The browser demonstration used generated media and a **fake** qBittorrent adapter.
The music dashboard was served by the bundled real music web app with an empty
temporary database. No production media, NAS paths, torrent sessions, or VPN state
were changed. The downloader browser container was not started locally.

Compose validation used Docker Compose 5.6.0; it emitted warnings that secret
UID/GID/mode metadata is ignored outside Swarm. Actual secret readability under
the NAS UID/group must be checked during deployment.

No local Docker daemon was available, so local image build/runtime and the Linux
container topology were **not** validated. CI includes Linux tests and image builds;
its live result is separate from the local results recorded here. NAS access,
qBittorrent live behavior, seeding preservation in a real client, actual disk mount
permissions, and VPN/kill-switch behavior still require deployment verification.

Primary integration references:
[qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29),
[Nginx auth subrequests](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html),
[FFmpeg builds](https://ffmpeg.org/download.html).
