# Changelog

## 0.4.0 - 2026-10-15

### Added

- Request-specific guided browser for Movie/TV requests using the existing
  authenticated Firefox/noVNC service.
- One-click request copying, configurable HTTPS discovery home, direct
  qBittorrent access, and return-to-request navigation.
- Authenticated single-request API and browser handoff tests.

### Security

- The browser retains its existing isolated mounts and receives no Movie/TV
  library, torrent-staging, qBittorrent credentials, or application secrets.
- Discovery-home configuration requires HTTPS without embedded credentials.
- Login, CAPTCHA, result selection, and qBittorrent attachment remain visible
  user actions.

## 0.3.0 - 2026-10-15

### Added

- Durable Movie/TV request inbox for names, HTTP(S) metadata links, and magnets.
- Request tracking from qBittorrent acquisition through automatic validation,
  reviewed import, and completion.
- Existing-torrent attachment for title/link requests and dashboard state views.
- Tests for the request lifecycle, private magnet redaction, and unsafe schemes.

### Security

- Magnet and tracker parameters remain server-side and are excluded from request
  and activity API responses.
- HTTP(S) request-link query strings and fragments are discarded before storage.

### Boundary

- Fox Den does not automatically select a torrent from a title in this release.
  Selection remains visible; validation and import safeguards remain unchanged.

## 0.2.1 - 2026-10-14

### Fixed

- Pass the existing CSRF and optional Jellyfin secrets directly from `.env` to
  Music containers. Environment-backed Compose secrets cannot be mounted into
  read-only services; the first container CI run caught this startup failure.
- Keep the WireGuard private key as a file-backed secret scoped to Gluetun.
- Stable CI permits only the two explicitly identified Windows-only test skips
  on Linux; all unexpected skips still fail the release gate.

## 0.2.0 - 2026-10-14

### Added

- Gluetun VPN and qBittorrent start with the main Docker Compose project.
- Central `VERSION` file supplies the authenticated status API and dashboard.
- Automated Compose checks cover VPN routing, health dependency, ports, secrets,
  capabilities, and shared staging mounts.
- Fresh-client login and existing-stack migration instructions.
- Layered CI for development and stable branches, with version consistency,
  test reports, container smoke tests, and stricter pre-merge release checks.

### Changed

- The bundled qBittorrent API is the default connection.
- Web UI port changes also update the client listener, firewall, and forwarding hooks.
- Fresh installs default Proton port forwarding to off until localhost hooks are
  configured. Existing explicit `.env` values remain effective.
- `compose.vpn.yaml` is now an empty compatibility shim.

### Upgrade

Configure VPN peer settings, private key file, and pre-created bind paths before
starting the main Compose file. Stop and back up an old torrent stack before
reusing its appdata. Set the qBittorrent password through its Web UI, then provide
it to Fox Den through `.env`. See [VPN setup](docs/torrent-vpn.md).

Local configuration checks passed; live VPN/NAS behavior is not yet verified.

## 0.1.0 - 2026-10-05

- Initial unified development build with shared login and navigation for Music
  2.3.4 and the movie/TV dashboard.
- qBittorrent controls, read-only staging, FFmpeg validation, reviewed verified
  copies, import receipts, recovery, and library checksum audits.
- Optional VPN Compose extension, environment configuration, and Linux CI.
