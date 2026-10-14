# Changelog

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
