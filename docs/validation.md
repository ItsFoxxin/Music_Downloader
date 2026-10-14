# Validation evidence

## Bundled VPN update - 2026-10-14

The first 0.2.0 CI run passed metadata, Compose, and Linux tests (34 media;
214 music with two Windows-only skips). Image builds passed, but container startup
exposed unsupported environment-backed secrets in read-only Music services.
Version 0.2.1 replaces those with the existing environment values and retains the
file-backed VPN key. See GitHub Actions for the latest commit's runtime result.

- Release 0.2.0 metadata, Python/JavaScript syntax, and workflow YAML checks passed.
- Local media tests: 30 passed, one Windows symlink case skipped, and three HTTP
  cases deselected after the Windows TestClient run stalled. The full HTTP suite
  must pass in Linux CI; the local partial run is not a full regression pass.
- New container smoke checks require Docker and were not executed locally.

- Main Compose configuration expands to all seven services without profiles.
- Automated topology checks passed for default port 8080 and custom port 8181:
  VPN namespace, healthy-start dependency, consistent Web UI/firewall/hook ports,
  key mount, restricted capabilities, shared downloads, and read-only app staging.
- The legacy two-file launch produces an identical expanded configuration.
- Four intentionally unsafe variants were rejected: host networking, writable
  app staging, optional qBittorrent profile, and mismatched download sources.
- The prior development commit's GitHub Actions run `37380626394` was checked
  and completed successfully. This does not validate the new commit's CI result.

These are configuration checks, not running-container tests. A local Docker daemon
was unavailable. Live NAS/VPN credentials, egress, kill-switch behavior, and actual
qBittorrent authentication remain deployment checks. CI now repeats the topology
checks as well as application tests and image builds.

## Original application verification

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
