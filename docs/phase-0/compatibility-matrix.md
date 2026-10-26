# Compatibility matrix

Status: Phase 0 baseline; live NAS state not verified  
Observed repository date: 2026-10-26

This matrix separates confirmed repository facts from target contracts. It is not a claim about the versions running on the NAS.

## Current repository baseline

| Component | Observed version/ref | State | Database/API | Current integration notes |
| --- | --- | --- | --- | --- |
| Standalone Music stable | v2.2.5, master/main at 84d3469 | Stable repository baseline | Music schema 2 | Independently deployable; default branch is still master |
| Standalone Music development | v2.5.1, dev at b4bbffb | Provisional; draft PR | Music schema 3 | Dev gate passed; strict PR gate is blocked by dependency audit |
| Bundled Music in Media | v2.3.4 in Media dev cc71b8e | Integrated copied source | Music schema 2 | Built from music/backend; not sourced from standalone image |
| Media application | v0.4.0, dev at cc71b8e | Development integration baseline | media.db with additive acquisition_id check; no explicit schema version | Movies/TV API and background worker share one process |
| Integrated gateway | nginx:stable-alpine moving tag | Development baseline | Media session subrequest | Root Music route and browser require Media session; all modules are mandatory |
| Standalone Music gateway | nginx:stable-alpine moving tag | Standalone baseline | No Media session dependency | Routes Music and browser |
| Contained browser | jlesage/firefox:latest moving tag | Optional in intent, mandatory in current Compose | noVNC/HTTP on 5800 | Shared profile and Music download inbox; no media library or Docker socket |
| qBittorrent | lscr.io/linuxserver/qbittorrent:latest moving tag | Mandatory in current Media Compose | Web API; code handles qBittorrent 4 and newer action naming | Shares Gluetun network namespace and /downloads mapping |
| Gluetun | qmcgaw/gluetun:v3.41.1 default | Mandatory in current Media Compose | Container health and WireGuard environment | Owns published qBittorrent Web UI port and NET_ADMIN |
| Jellyfin | External, unpinned | Optional | Library refresh API | Music worker only; URL/key may be blank |

Current compatibility must not be inferred beyond these observed sources. The actual NAS image digests, schemas, mounts, credentials, and service versions require the read-only inventory.

## Target release matrix fields

Every integrated Media release must publish:

| Field | Requirement |
| --- | --- |
| Media version and commit | Exact semantic version and source commit |
| Media database range | Minimum, maximum, forward migration, and rollback rule |
| Music version | Exact released semantic version |
| Music image | Registry, immutable digest, source tag, and source commit |
| Music database range | Minimum and maximum supported schema versions |
| Gateway | Exact image digest and configuration revision |
| Browser | Exact image digest, optional capability state, and supported route contract |
| qBittorrent | Tested server version/API range and whether external or managed |
| Gluetun | Tested image digest and supported VPN mode; not applicable for external qBittorrent |
| Jellyfin | Tested API behavior or explicitly untested optional state |
| Architectures | Tested CPU architectures; no implied support for untested platforms |
| Deployment modes | Passing acceptance results for each advertised mode |
| Configuration contract | Supported variable-set version and deprecations |
| Migration | Source versions, required backups, and rollback procedure |

## Target compatibility rules

### Music image

- Media consumes only a released standalone Music image that passes the Music image acceptance criteria.
- Media pins the image digest.
- Media integration tests may exercise a release candidate, but an integrated stable release may not pin an unapproved development build.
- A Music schema outside the published supported range must fail before a worker claims jobs or writes library data.

### Gateway and authentication

- Music Only has no dependency on a Media session endpoint.
- Movies/TV Only has no dependency on a Music health endpoint.
- Full mode may use a shared login, but authentication failure must be distinguishable from an unavailable optional module.
- Reverse-proxy base URL, trusted-forwarded-header behavior, HTTPS, and secure-cookie settings are environment-driven and mode-validated.
- The browser and qBittorrent are not independently exposed by default in Full mode.

### Browser

- Browser absence must not prevent non-browser workflows from starting.
- Media handoff remains human-controlled and receives no torrent credentials, Docker socket, application database, or media-library mount.
- A shared browser may mount the Music download inbox only in modes that enable Music acquisition.
- Browser image and profile migrations must be documented before changing the pinned version.

### qBittorrent and VPN

- External qBittorrent is supported without Gluetun configuration.
- Managed qBittorrent preserves the exact container-side download root used in resume data.
- Managed VPN requires a healthy Gluetun service before qBittorrent starts.
- qBittorrent and Gluetun image upgrades are separate from application/database migrations unless explicitly tested together.
- Moving latest tags are development conveniences only and are not accepted release pins.

### Jellyfin and metadata providers

- Jellyfin disabled is a valid state with no URL or key.
- MusicBrainz configuration belongs to Music modes only.
- Optional Spotify, AcoustID, or other provider credentials are validated only when their feature is enabled.
- Metadata-provider outages must not make local library browsing or already validated import history unavailable.

## Environment-variable compatibility

Environment names and semantics are a public deployment contract.

During migration:

- existing CONFIG_PATH, STAGING_PATH, MUSIC_PATH, DOWNLOAD_INBOX_PATH, BROWSER_CONFIG_PATH, MEDIA_CONFIG_PATH, TORRENT_STAGING_PATH, MEDIA_PATH, TORRENT_CONFIG_PATH, GLUETUN_CONFIG_PATH, PUID, PGID, FILE_UMASK, TZ, WEB_BIND_IP, WEB_PORT, Jellyfin, MusicBrainz, qBittorrent, and WireGuard variables remain recognized;
- module-specific examples contain only relevant settings;
- replacement names require at least one documented deprecation cycle or an explicit migration transformer;
- secret-file forms may be added without removing compatible direct-value forms until the migration release documents the transition;
- disabled modules must not trigger required-variable interpolation;
- CI renders every supported mode with only its declared environment file;
- no example contains a developer path or populated secret.

## Known incompatibilities and blockers

- Music schema 3 cannot be assumed rollback-compatible with v2.2.5/schema 2. A schema-2 config backup is required before upgrade.
- The current Media gateway cannot provide Music Only because its auth check depends on Media.
- The current Media Compose cannot omit qBittorrent, Gluetun, browser, or either application module.
- The bundled Music 2.3.4 and standalone Music 2.5.1 are not interchangeable source trees.
- The current qBittorrent and browser moving tags do not provide reproducible release compatibility.
- The current Media database needs explicit schema metadata before significant migrations.
- NAS filesystem, VPN, qBittorrent appdata, reverse proxy, and ownership compatibility remain unverified.
