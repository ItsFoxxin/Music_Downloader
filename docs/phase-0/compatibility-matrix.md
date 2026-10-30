# Compatibility matrix

Status: Revised Phase 0 baseline; live NAS state not verified  
Observed repository date: 2026-10-26

## Current source baseline

| Component | Observed ref | Role in consolidation | Rule |
| --- | --- | --- | --- |
| Music_Downloader stable | v2.2.5, master/main at 84d3469, schema 2 | Historical stable Music baseline | Preserve history; do not use as newer source |
| Music_Downloader development | v2.5.1, dev at b4bbffb, schema 3 | Authoritative Music foundation | Independent release work must finish first |
| Music draft PR | dev to main, draft | Active independent work | Resolve before rename/path migration |
| Media bundled Music | v2.3.4 in Media dev | Obsolete duplicate | Exclude from history import and active source |
| Media Movies/TV | v0.4.0, Media dev cc71b8e | Authoritative Movies/TV source | Import unique history |
| Phase 0 revision | Media dev after 41b23ce | Architecture provenance | Import approved Portal/architecture work later |
| Media gateway | nginx stable-alpine configuration | Ingress input | Reconcile with Portal auth; do not copy blindly |
| Music gateway | nginx stable-alpine configuration | Upload/browser input | Reconcile with platform ingress |
| Browser | jlesage/firefox latest | Optional shared infrastructure | Pin tested image before stable release |
| qBittorrent | LinuxServer latest | External or managed torrent service | Record tested API/version and pin managed image |
| Gluetun | v3.41.1 default | Optional managed VPN | Pin digest and host-test VPN behavior |
| Jellyfin | External | Optional integration | Never required for platform startup |

These are repository observations, not claims about the NAS.

## Target monorepo compatibility record

Every platform release records:

- platform semantic version and source commit;
- Portal, Music, Media, ingress, and browser image digests;
- Portal, Music, and Media database schema ranges;
- contract-schema and environment-contract versions;
- tested qBittorrent API/application range;
- tested Gluetun image/VPN mode;
- tested Jellyfin behavior;
- supported CPU architectures;
- passing deployment modes;
- supported source upgrade versions and rollback requirements.

All first-party images are produced from one platform release commit. Database schemas retain independent versions.

## Portal/module contract compatibility

| Consumer | Provider | Required behavior |
| --- | --- | --- |
| Portal | Music | Versioned capability, health, activity, and navigation API |
| Portal | Movies/TV | Same contract; independent timeout/failure handling |
| Ingress | Portal | Session validation/auth decision |
| Music | Portal/ingress | Verified internal identity assertion in integrated mode |
| Movies/TV | Portal/ingress | Verified internal identity assertion in integrated mode |
| Portal | Disabled module | No request; module hidden |
| Portal | Unhealthy module | Bounded failure; module shown unhealthy; Portal stays healthy |

No consumer reads another module database.

## Deployment-mode configuration compatibility

| Mode | Required groups | Explicitly not required |
| --- | --- | --- |
| Music Only | platform, Portal, Music paths/runtime | Media, qBittorrent, Gluetun, VPN |
| Movies/TV external | platform, Portal, Media, external qBittorrent mapping | Music, MusicBrainz, Gluetun, VPN |
| Full external | platform, Portal, Music, Media, external qBittorrent | managed Gluetun/WireGuard |
| Full Managed | platform, Portal, Music, Media, browser, qBittorrent, Gluetun | external client ownership |
| Any without Jellyfin | selected modules only | Jellyfin URL/key |
| Any without browser | selected modules only | browser profile/port/provider home |

Disabled groups must not be interpolated, validated, mounted, or health-gated.

## Existing-variable migration

The monorepo migration retains compatibility mappings for existing documented variables, including paths, PUID/PGID, umask, timezone, web binding, Music providers, Jellyfin, browser, Media, qBittorrent, and WireGuard settings.

Rules:

- semantics do not change silently;
- replacement names have a documented compatibility period;
- module-specific examples contain no irrelevant variables;
- direct secrets gain file-based forms before direct forms are deprecated;
- preflight reports deprecated names without values;
- CI renders old-variable fixtures and new module-scoped fixtures;
- no developer or NAS-specific value is required.

## Repository and artifact compatibility

A repository rename preserves most GitHub repository information and git redirects, but the migration checklist separately verifies:

- open PR disposition;
- Actions and reusable-action references;
- badges and raw links;
- Pages;
- releases and tags;
- branch rules and default branch;
- environments and secrets names;
- webhooks and deployment integrations;
- GHCR image naming, association, and permissions;
- local clone remotes;
- old-name non-reuse.

## Known blockers

- Music strict release gate currently has a dependency-audit failure.
- Music active PR/default-branch state is not ready for rename.
- Portal and module contracts do not yet exist.
- Current Media auth depends on Movies/TV and violates the Portal requirement.
- Current Media Compose makes all services mandatory.
- Moving browser/qBittorrent/gateway tags are not reproducible.
- Media database lacks explicit schema metadata.
- Live NAS versions, paths, mounts, permissions, filesystem behavior, VPN, and qBittorrent state remain unverified.
