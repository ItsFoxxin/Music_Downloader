# Monorepo source ownership map

Status: Target ownership; paths may be refined without weakening boundaries

| Target area | Authoritative source | Owner | Must preserve | Must not absorb |
| --- | --- | --- | --- | --- |
| apps/portal | New first-class component, initially developed independently in Media history | Platform | auth, sessions, module registry, health/activity aggregation, degraded UI | Music/Media DB access, media mounts, qBittorrent/VPN secrets |
| apps/music | Music_Downloader dev after independent release checkpoint | Music | web/worker split, request workflow, MusicBrainz, tagging, validation, atomic import, inventory, Jellyfin refresh | Media_Downloader music subtree |
| apps/media | Media_Downloader dev app plus relevant tests | Movies/TV | qBittorrent API, validation, receipts, no-overwrite import, interrupted-job recovery | Music business logic or Music database |
| contracts | New versioned schemas | Platform with module review | capabilities, health, activity, auth assertion, config contract | ORM models or shared DB schemas |
| infra/gateway | Media gateway behavior plus standalone Music upload/browser requirements | Platform/security | buffering, websocket, timeouts, auth request, mode routes | Portal product logic or credentials |
| infra/browser | Media/Music handoff assets and container policy | Platform/security | human control, isolation, optional profile/download handoff | CAPTCHA automation, Docker socket, media libraries, qBittorrent credentials |
| deploy/music | Derived from current standalone Music deployment | Operations/Music | non-root web/worker, mounts, secrets, health | Media/VPN required variables |
| deploy/media | Derived from Media app deployment | Operations/Media | read-only torrent staging, media config/library | Music required variables |
| deploy/full | New composition | Platform/operations | simple launch, Portal, isolation, external/managed variants | duplicated app definitions |
| deploy/torrent | Media qBittorrent/Gluetun configuration | Operations/security | network namespace, kill switch, appdata/download mapping | application DB or library ownership |
| tests/music | Music_Downloader tests | Music | schema, import, UI, browser, compatibility gates | obsolete bundled expectations |
| tests/media | Media_Downloader tests | Media | qBittorrent, validation, import, request flows | copied Music tests |
| tests/portal | New | Platform | disabled/unhealthy modules, auth, aggregation, navigation | live provider/NAS assumptions |
| tests/integration | Both repositories plus new fixtures | Platform | all deployment modes, contracts, isolation, portability | production secrets or paths |
| docs | Both repositories, reconciled | Platform with module owners | migration, limitations, examples, evidence labels | conflicting duplicate instructions |

## Database ownership

| Database | Owner process | Readers | Migration owner |
| --- | --- | --- | --- |
| portal.db or approved Portal store | Portal | Portal only | Portal |
| foxden-music.db | Music web/worker through Music data layer | Music only | Music |
| media.db | Movies/TV service and future worker through Media data layer | Media only | Media |
| qBittorrent appdata | qBittorrent | qBittorrent only; API clients use HTTP | qBittorrent image/operator |
| Jellyfin database | Jellyfin | Jellyfin only | Jellyfin/operator |

Portal obtains summaries through HTTP contracts. It never mounts application config directories.

## Configuration ownership

- Platform owns enable flags, ingress, Portal, public URLs, trusted proxies, common UID/GID/timezone conventions, and mode selection.
- Music owns Music paths, metadata providers, acquisition, scan/import, and Music Jellyfin behavior.
- Media owns Movies/TV paths, qBittorrent client mapping, validation/import, and Media-specific integrations.
- Torrent infrastructure owns VPN, Web UI, appdata, port forwarding, and download-root settings.
- Browser owns profile and browser-only settings.
- Secrets remain scoped to the narrowest consumer.

## Conflict rules

1. Newer Music_Downloader dev wins every Music source conflict.
2. Media_Downloader music is never used as an implementation source.
3. Media unique application behavior wins Movies/TV conflicts.
4. Portal authentication replaces Media-owned platform authentication, but Media may retain module authorization.
5. Ingress behavior is reconciled; neither existing gateway file is copied blindly.
6. Existing database columns and state meanings are preserved unless a separately approved migration changes them.
7. Existing environment variables receive compatibility mappings before any rename or removal.
