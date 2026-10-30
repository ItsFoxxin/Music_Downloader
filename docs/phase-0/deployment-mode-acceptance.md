# Deployment-mode and Portal acceptance criteria

Status: Revised Phase 0 test contract; not implemented

## Common platform criteria

Every advertised mode must:

- render, preflight, and start from documented environment examples without source or Compose edits;
- start ingress and Portal;
- require only enabled-module variables;
- honor custom paths, ports, bind addresses, UID/GID, umask, timezone, proxy URLs, and secret files;
- preserve non-root/read-only/capability isolation;
- expose no undocumented port;
- never log secrets;
- survive normal restart;
- distinguish disabled, unavailable, unhealthy, and healthy modules;
- keep Portal usable when any module is absent or unhealthy;
- use separate module databases and mounts;
- pass CI with synthetic data only.

## Portal acceptance

- Login, logout, session expiry, secure-cookie behavior, CSRF protection, and authorization pass.
- Portal starts with zero enabled media modules and presents a coherent platform/setup page.
- Disabled modules are hidden from navigation and activity.
- Enabled healthy modules show current version and navigation.
- Enabled unhealthy/unreachable modules show a clear degraded status without delaying or crashing the page.
- Music failure does not disable Movies/TV navigation.
- Movies/TV failure does not disable Music navigation.
- Browser, qBittorrent, Gluetun, metadata-provider, and Jellyfin failures are scoped to their features.
- Health/activity calls use bounded timeouts and sanitized data.
- Portal has no Music/Media database, library, torrent, VPN, or browser-profile mount.
- Portal authentication has no dependency on Movies/TV.
- Modules reject spoofed client identity headers and accept only the approved internal assertion.
- Combined activity tolerates missing, malformed, old-contract, and slow module responses.

## Music Only

Containers: ingress, Portal, Music web, Music worker; optional browser.

- No Media, qBittorrent, Gluetun, VPN, Movies, or TV configuration.
- Gateway auth uses Portal.
- Direct test upload validates and imports atomically.
- Existing destination is refused.
- Library scan/history survives restart.
- Jellyfin-disabled and browser-disabled paths pass.
- Portal reports Music health/activity and hides Movies/TV.
- Simulated Music failure leaves Portal login and setup/status usable.

## Movies/TV Only with external qBittorrent

Containers: ingress, Portal, Movies/TV; optional browser.

- No Music path, MusicBrainz, Music worker, Gluetun, or WireGuard configuration.
- External qBittorrent mapping is validated.
- Torrent staging is read-only to Media.
- Completed synthetic media validates and imports without removing the seeding source.
- Incomplete, unsafe, moved, and out-of-root payloads fail.
- Portal reports Media health/activity and hides Music.
- qBittorrent unavailability degrades acquisition without disabling Portal.

## Full with external qBittorrent

Containers: ingress, Portal, Music web, Music worker, Movies/TV; optional browser.

- Music and Media flows pass independently.
- External qBittorrent remains authoritative.
- No Gluetun/WireGuard variables are required.
- Combined activity has stable ordering and identifies source module.
- Failure injection proves either module can fail without taking down Portal or the other module.
- Authentication and navigation remain coherent across interfaces.

## Full Managed

Eight containers: ingress, Portal, Music web, Music worker, Movies/TV, Firefox, qBittorrent, Gluetun.

- One documented command renders and starts the complete platform after environment preparation.
- Gluetun health gates qBittorrent.
- qBittorrent shares Gluetun networking and has no independent published network.
- Only Gluetun receives NET_ADMIN and /dev/net/tun.
- Browser has no application databases, libraries, Docker socket, qBittorrent credentials, or VPN secret.
- Music and Movies/TV test imports both pass.
- Source torrent remains available for seeding.
- Gateway login/logout, HTTPS forwarding, upload, and browser websocket tests pass.
- Restart/dependency recovery passes.
- No service exposes an undocumented port.
- Real VPN egress, kill switch, port forwarding, NAS mounts, and Jellyfin remain host acceptance tests, not CI claims.

## Portability and compatibility CI

Future CI covers:

- every mode using only its declared example;
- negative tests for disabled-service variables;
- custom ports, bind addresses, storage paths, UID/GID, umask, and timezone;
- secret-file and redacted-error behavior;
- missing/unreadable/unwritable/overlapping/cross-device paths;
- HTTP versus HTTPS/trusted-proxy validation;
- external and managed qBittorrent;
- browser/Jellyfin enabled and disabled;
- existing environment-variable compatibility;
- repository scan for developer paths, private examples, secrets, and moving stable tags;
- non-root identities, exact mounts, capabilities, networks, and health;
- Portal/module contract versions and failure injection;
- supported CPU architectures once approved.

Evidence labels distinguish parsed, preflighted, tested, container-started, artifact-published, shadow-tested, NAS-tested, and live-integration-tested.
