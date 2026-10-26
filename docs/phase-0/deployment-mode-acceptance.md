# Deployment-mode acceptance criteria

Status: Phase 0 test contract; not yet implemented

## Common acceptance rules

Every advertised mode must:

- render and validate from its documented example without editing source or Compose YAML;
- require only variables belonging to enabled modules;
- use documented safe defaults and placeholder-only examples;
- honor custom host paths, ports, bind addresses, UID/GID, umask, and timezone;
- preflight missing paths, permissions, invalid URLs/ports, overlapping roots, and unsafe exposure;
- never print secret values;
- start enabled services independently of disabled modules;
- expose only documented ports;
- run application services non-root with current isolation controls;
- provide health and capability status that distinguishes disabled, unavailable, and unhealthy;
- survive a normal restart without losing completed state;
- provide exact backup and rollback requirements;
- pass on supported Linux CI and be clearly marked unverified on platforms not exercised.

CI uses temporary paths and synthetic/test media. It never uses NAS state or real credentials.

## Music Only

### Configuration

- Requires Music config, staging, and library paths.
- Download inbox is configurable and may be enabled independently of the browser.
- Does not require Media paths, qBittorrent, Gluetun, WireGuard, torrent ports, or APP_TOKEN from the Media application.
- MusicBrainz contact is required only for network metadata lookup; incoming-tag/manual paths explain reduced behavior when absent.
- Jellyfin, Spotify, AcoustID, Chromaprint, and browser are independently optional.
- Supports documented direct or reverse-proxied bind settings.

### Topology and isolation

- Starts Music web and worker plus only explicitly selected gateway/browser services.
- Music web cannot write the real library.
- Music worker can write the Music library but has no torrent appdata, VPN device, or Docker socket.
- Browser-disabled mode has no browser dependency or browser port.
- Gateway authentication does not call the absent Media service.

### Functional test

- Health endpoints pass.
- Fresh database initializes.
- Supported copied database migrates without losing history.
- Direct test upload validates and imports atomically.
- Existing destination is refused.
- Library scan reports the test import.
- Restart preserves history and inventory.
- Jellyfin-disabled mode completes without a key.
- Browser-enabled test verifies same-origin routing; browser-disabled test verifies ordinary imports still work.

## Movies/TV Only with external qBittorrent

### Configuration

- Requires Media config, torrent-staging mapping, Movies/TV library paths, application authentication, and qBittorrent connection settings.
- Does not require Music config/library paths, MusicBrainz, Spotify, AcoustID, Music worker variables, Gluetun, or WireGuard.
- qBittorrent internal URL, browser-reachable URL, credentials/secret file, and exact container-side download root are independently validated.
- Browser and Jellyfin remain optional unless a future Media feature explicitly enables them.

### Topology and isolation

- Starts Media and selected gateway/browser services.
- Does not start Music web/worker, qBittorrent, or Gluetun.
- Media sees torrent payloads read-only.
- Media alone writes Movies/TV destinations.
- Existing external qBittorrent remains authoritative for appdata and networking.
- Gateway routes do not require Music health.

### Functional test

- Connects to a disposable external qBittorrent fixture.
- Maps a completed torrent path from qBittorrent root to read-only staging.
- Rejects incomplete, moved, unsafe, or out-of-root payloads.
- Validates synthetic media.
- Imports to a disposable library with receipt and no-overwrite behavior.
- Leaves source payload in place for seeding.
- Restart reconciles documented interrupted states.
- qBittorrent unavailability produces a clear degraded/error state without corrupting Media state.

## Movies/TV Only with managed torrent/VPN

In addition to external-qBittorrent criteria:

- Gluetun settings are required only when the managed VPN overlay is selected.
- qBittorrent shares Gluetun’s network namespace and publishes no independent network path.
- Gluetun health gates qBittorrent startup.
- Only Gluetun receives NET_ADMIN and /dev/net/tun.
- qBittorrent Web UI exposure defaults to loopback or gateway-protected access.
- CI validates topology and health with safe fixtures; a real VPN egress/kill-switch test is documented as environment acceptance.
- Disabling managed VPN in favor of an external client removes every WireGuard requirement.

## Full Managed

### Configuration

- Combines module-specific environment files without redefining variable meanings.
- Requires Music variables, Media variables, and managed torrent/VPN variables.
- Optional Jellyfin and browser settings remain independently selectable.
- Host paths are checked for unintended overlap.
- Custom ports and reverse-proxy URLs are honored without Compose edits.
- No personal address/path/domain appears in defaults.

### Topology and isolation

- Starts gateway, Music web, Music worker, Media, selected browser, qBittorrent, and Gluetun.
- Gateway provides coherent Music, Movies/TV, and browser routes.
- Shared authentication does not grant backend services unnecessary secrets.
- Music and Media retain separate databases, staging areas, and final-library ownership.
- qBittorrent appdata is writable only by qBittorrent.
- Torrent staging is read-only to Media.
- Browser has no Docker socket, torrent credentials, application databases, or media-library mounts.
- Failure of Music does not corrupt Media; failure of Media does not corrupt Music.
- Browser unavailability does not prevent non-browser operations.

### Functional test

- All health and capability checks report the expected topology.
- Music test import and Movie/TV test import both pass.
- Databases and histories remain independent.
- Gateway login, logout, forwarded HTTPS, secure cookies, and websocket browser route pass.
- qBittorrent download-root mapping and source-preserving import pass.
- Gluetun/qBittorrent topology validation passes.
- Restart order and dependency recovery pass.
- Disabled Jellyfin path passes with no credentials.
- Optional mocked Jellyfin refresh passes when enabled.
- No service exposes an undocumented port.

## Environment and portability CI

Future CI must include:

- Compose parsing for every mode using only its example environment.
- Negative tests proving disabled modules need no variables.
- Custom bind address and nondefault-port rendering.
- Custom absolute storage-path rendering.
- UID/GID, umask, and timezone overrides.
- Secret-file path behavior and redacted failures.
- nonexistent, unreadable, non-writable, overlapping, and cross-device path preflight fixtures.
- reverse-proxy HTTP versus HTTPS/secure-cookie validation.
- external versus managed qBittorrent configurations.
- browser enabled and disabled.
- Jellyfin enabled and disabled.
- compatibility fixtures for existing environment-variable names.
- a repository scan rejecting developer home paths, private IP examples, populated credentials, and moving release tags in stable manifests.
- container smoke confirming non-root identity, mounts, health, and absence of unnecessary capabilities.
- supported CPU architecture build tests once the architecture support decision is made.

## Evidence labels

Release reports must distinguish:

- configuration parsed;
- preflight passed;
- unit/integration tests passed;
- containers started in CI;
- published artifact verified;
- shadow deployment tested;
- NAS deployment tested;
- real VPN/qBittorrent/Jellyfin/provider workflow tested.

One label must never be used as proof of another.
