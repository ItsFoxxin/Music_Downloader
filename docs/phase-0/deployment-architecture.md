# Target deployment architecture

Status: Phase 0 design; not implemented

## Full Managed topology

External reverse proxy or client
  -> ingress
     -> Portal
     -> Music web
     -> Movies/TV
     -> contained browser

Music worker
  -> Music database, staging, inbox, Music library
  -> optional metadata providers and Jellyfin

Movies/TV
  -> Media database
  -> qBittorrent HTTP API
  -> read-only torrent staging
  -> Movies and TV libraries

qBittorrent
  -> Gluetun network namespace
  -> qBittorrent appdata and torrent downloads

Portal queries versioned health/activity APIs over the internal application network. It does not mount the module databases or libraries.

## Networks

Recommended logical networks:

- edge: ingress to Portal and selected application HTTP endpoints;
- app: Portal to Music/Media contract endpoints and internal service communication;
- torrent: qBittorrent shares Gluetun network namespace rather than joining as an independently addressable service.

Database and filesystem traffic uses bind mounts, not network sharing. The exact Docker networks remain subject to implementation threat modeling.

## Authentication flow

1. Client reaches ingress.
2. Public login assets route to Portal.
3. Protected routes use Portal authentication/session validation.
4. Ingress forwards authenticated module requests with a signed or otherwise integrity-protected internal identity assertion.
5. Modules validate the assertion and do not trust arbitrary client-supplied forwarded identity headers.
6. Portal logout invalidates the platform session.
7. If a module is unavailable, Portal remains reachable and reports degradation.

External reverse proxies terminate TLS according to documented trusted-proxy settings. HTTPS and secure-cookie behavior are validated during preflight.

## Portal module contract

Every module exposes versioned internal endpoints for:

- capability identity and version;
- health with bounded detail;
- enabled features;
- recent read-only activity;
- navigation target;
- optional counts safe to expose.

The contract excludes secrets, host paths, provider tokens, torrent tracker data, stack traces, and raw database records.

Portal uses short timeouts, parallel bounded requests, circuit breaking/backoff, and cached last-known status where appropriate. A failed response never crashes the homepage.

## Deployment modes

### Music Only

Containers:

- ingress;
- Portal;
- Music web;
- Music worker;
- optional browser.

No Media, qBittorrent, Gluetun, Movies/TV paths, or VPN settings required.

### Movies/TV Only with external qBittorrent

Containers:

- ingress;
- Portal;
- Movies/TV;
- optional browser.

External qBittorrent URL and exact download mapping are required for torrent workflows. Music and VPN variables are absent.

### Full with external qBittorrent

Containers:

- ingress;
- Portal;
- Music web;
- Music worker;
- Movies/TV;
- optional browser.

No managed Gluetun or qBittorrent containers. External qBittorrent remains authoritative.

### Full Managed

Eight containers:

- ingress;
- Portal;
- Music web;
- Music worker;
- Movies/TV;
- contained browser;
- qBittorrent;
- Gluetun.

The target user experience is one documented command using prepared environment files. The effective Compose topology remains inspectable before launch.

## Storage mounts

Portal:

- Portal config/database only, if persistence is selected.

Music web:

- Music config;
- Music staging;
- optional download inbox;
- no real Music library.

Music worker:

- Music config;
- Music staging;
- optional download inbox;
- Music library.

Movies/TV:

- Media config;
- read-only torrent staging;
- Movies and TV libraries.

Browser:

- browser profile;
- optional Music download inbox only when that acquisition feature is enabled.

qBittorrent:

- qBittorrent appdata;
- torrent downloads.

Gluetun:

- Gluetun config;
- WireGuard secret file.

Ingress:

- generated/static mode configuration only.

All host paths are environment-driven and validated. No personal NAS path is embedded.

## Failure behavior

- Portal unavailable: module APIs may remain healthy internally, but platform UI is unavailable; ingress health reports the distinction.
- Music unavailable: Portal shows Music unhealthy and keeps Movies/TV navigation active.
- Movies/TV unavailable: Portal shows it unhealthy and keeps Music active.
- Browser unavailable: browser actions are disabled/degraded; upload/inbox/manual workflows continue where supported.
- qBittorrent unavailable: Movies/TV acquisition reports degraded; Music and Portal continue.
- Gluetun unavailable: managed qBittorrent remains stopped/unhealthy; non-torrent modules continue.
- Jellyfin unavailable: imports remain valid and refresh is retryable.
- metadata provider unavailable: local library and history remain available.

## Platform limitations to document

- SQLite config paths require local filesystem locking behavior.
- Atomic library publication requires compatible same-filesystem no-replace rename.
- NAS Compose implementations, rootless VPN devices, SELinux/AppArmor, NFS/SMB semantics, and CPU architectures are supported only when tested.
- Existing qBittorrent resume paths must preserve container-side mappings.
- Real VPN kill-switch and port-forward behavior requires host-level acceptance testing.
