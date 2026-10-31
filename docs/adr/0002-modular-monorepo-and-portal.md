# ADR 0002: Modular monorepo with an independent Portal

- Status: Accepted architecture; implementation pending
- Decision date: 2026-10-26
- Scope: Canonical repository, source ownership, Portal, processes, releases, deployment modes, and portable configuration
- Supersedes: ADR 0001
- Approved option: Option B, modular monorepo

## Context

Fox Den Music and Fox Den Movies/TV evolved in separate repositories. Media_Downloader also contains an obsolete copied Music tree, while Music_Downloader dev contains the newer Music implementation and active work.

The desired product is one cohesive Fox Den Media platform, not two products joined by a dashboard. It needs one canonical source repository and release process while retaining separate application processes, databases, workers, mounts, and privilege boundaries.

The platform must remain deployable in smaller modes. Disabled modules must not introduce configuration requirements or prevent the Portal from operating.

## Decision

### Canonical repository

The target is one repository named FoxDen_Media.

Music_Downloader is the recommended repository lineage to rename because:

- its dev branch is the authoritative Music implementation;
- it contains the active Music branches, pull request, tests, and release history;
- using it as the foundation avoids copying an older Music implementation over newer work;
- a GitHub repository rename preserves the repository object and most history and links.

The rename must not occur while the independent Music task has an unresolved release gate or open migration-sensitive pull request. The exact rename, default-branch changes, and repository settings require a separate approval and maintenance checklist.

Media_Downloader remains intact until the consolidation has passed every acceptance gate. Its non-Music history is imported into the canonical repository through a reviewed filtered-history procedure. Its music directory is excluded and never overlays the authoritative Music source.

### Target source layout

The target logical layout is:

- apps/portal: platform homepage, authentication, module registry, health aggregation, activity aggregation, and navigation;
- apps/music: authoritative Music web, worker, library, acquisition, metadata, and import implementation;
- apps/media: Movies/TV web/API and worker behavior;
- contracts: versioned module capability, health, activity, authentication, and configuration schemas;
- infra/gateway: ingress-only routing, buffering, websocket, upload, and auth-request configuration;
- deploy: modular Compose entrypoints, environment examples, preflight assets, and migration examples;
- tests/integration: deployment-mode, contract, gateway, failure-isolation, and portability tests;
- docs: architecture, operation, security, release, migration, and platform limitations.

Exact Python packaging may evolve, but ownership boundaries are fixed by the source ownership map.

### Portal

Portal is a first-class platform application, not merely a reverse proxy.

Portal owns:

- login, logout, sessions, and platform authorization;
- platform homepage and navigation;
- enabled-module registry;
- module capability and health aggregation;
- combined read-only activity summaries;
- degraded-state presentation;
- links into integrated Music and Movies/TV interfaces;
- its own configuration and, if persistence is needed, its own database and schema.

Portal must:

- start and remain usable when Music, Movies/TV, browser, qBittorrent, Gluetun, or Jellyfin is disabled or unavailable;
- hide intentionally disabled modules;
- show enabled but unhealthy or unreachable modules clearly;
- use bounded timeouts and failure isolation when querying modules;
- never read a Music or Media SQLite database directly;
- never depend on Movies/TV authentication;
- avoid receiving Music-library, media-library, torrent-appdata, VPN, or browser-profile mounts;
- avoid receiving qBittorrent, Jellyfin, or provider credentials unless a narrowly approved Portal feature needs them.

Music and Movies/TV expose versioned, read-only Portal APIs for capability, health, and activity. Portal authentication is authoritative for the integrated platform. Modules may keep internal authorization checks and trust only a documented internal identity assertion from Portal/ingress.

### Ingress

Ingress and Portal remain conceptually separate:

- ingress owns HTTP routing, body buffering rules, websocket forwarding, timeouts, and auth subrequests;
- Portal owns product UI, sessions, authorization decisions, health/activity aggregation, and navigation.

Full Managed therefore targets eight primary containers without combining privilege boundaries:

1. ingress;
2. Portal;
3. Music web;
4. Music worker;
5. Movies/TV application with its current internal worker;
6. optional contained Firefox;
7. qBittorrent;
8. Gluetun.

A future separate Movies/TV worker would make nine containers and requires a later reliability decision. It is not part of initial consolidation.

### Runtime and data isolation

- Portal, Music, and Movies/TV have separate databases.
- Music worker alone mutates the Music library.
- Movies/TV alone mutates Movies and TV libraries.
- qBittorrent alone owns its appdata and resume state.
- Gluetun owns VPN networking and credentials.
- Browser receives only its profile and explicitly required download handoff.
- Ingress receives no application database, media mount, or provider secret.
- No module accesses another module database.
- Cross-module behavior uses versioned contracts.
- Old and new deployments never write concurrently to the same state.

### Deployment modes

The repository must support:

- Music Only: ingress, Portal, Music web, Music worker; browser and Jellyfin optional.
- Movies/TV Only: ingress, Portal, Movies/TV; external qBittorrent required for torrent workflows, browser/Jellyfin optional when supported.
- Full External Torrent: ingress, Portal, Music web/worker, Movies/TV, external qBittorrent; browser/Jellyfin optional.
- Full Managed: eight-container platform with ingress, Portal, Music web/worker, Movies/TV, browser, qBittorrent, and Gluetun.
- Managed Movies/TV is also permitted as a documented composition if it passes the same isolation gates.

A simple full-platform command is required. The command may combine a base file and one explicit managed overlay, but users must not edit Compose YAML.

### Environment-driven portability

ADR 0001 environment requirements remain part of the decision, now owned by the monorepo:

- module-scoped environment files;
- host paths, UID/GID, umask, timezone, bind addresses, ports, public URLs, reverse-proxy and HTTPS settings;
- module-specific metadata and acquisition settings;
- optional Jellyfin, browser, external qBittorrent, and managed Gluetun settings;
- direct-value compatibility plus documented secret-file forms;
- resource limits and operational settings only where users benefit;
- no personal paths, IPs, domains, accounts, or secrets in source;
- mode-aware preflight with redacted actionable errors;
- no variables for disabled modules;
- safe loopback exposure by default;
- supported Linux Docker and NAS environments documented by tested capability rather than vendor promises.

Environment variables are a versioned public interface. Internal settings are not exposed solely for configurability.

### Versioning

The monorepo publishes one platform version and coordinated artifacts from one commit.

- Repository tags use platform semantic versions.
- Portal, Music, and Media images are built from the same platform release commit and carry the platform version and source SHA.
- Database schema versions remain independent per application.
- Contract schemas have explicit versions.
- Compatibility metadata records platform version, image digests, schema ranges, configuration-contract version, tested qBittorrent/Gluetun/browser versions, CPU architectures, and deployment modes.
- Historical Music versions and schema lineage remain documented through the consolidation.
- A major platform version is appropriate for the first production monorepo release; its exact number requires approval.
- Moving image tags are not stable release inputs.

### History preservation

- Existing Music commits, tags, branches, releases, and PR context remain in the canonical lineage.
- Media unique history is filtered to exclude music and imported under namespaced paths.
- Filtered history preserves authors, dates, and messages where practical, while rewritten commit IDs are recorded against the original source head.
- The original repositories remain available throughout migration and validation.
- Media_Downloader is not archived or made read-only until post-cutover approval.
- No old repository name is reused because doing so can break GitHub redirects.
- Workflows, badges, reusable-action references, package associations, Pages URLs, webhooks, deployment keys, branch rules, and external integrations are audited explicitly rather than assumed to follow a rename.

## Consequences

Benefits:

- one product backlog, release, security policy, CI model, documentation set, and deployment command;
- one authoritative Music source;
- Portal can evolve independently of either media module;
- atomic cross-module contract changes are possible;
- modular runtime isolation remains;
- users select only the services they need.

Costs:

- repository consolidation is more disruptive than image composition;
- CI must avoid running every expensive suite for unrelated changes while retaining full release gates;
- source layout changes can conflict with active Music development;
- history filtering and repository rename need rehearsals;
- a first-class Portal adds a service and its own security responsibility;
- coordinated platform releases require careful schema and rollback metadata.

## Rejected alternatives

- ADR 0001 separate product repositories: rejected because the desired product is one cohesive application.
- Use Media_Downloader as canonical and overwrite its Music tree: rejected because its Music implementation is obsolete.
- Import the entire Media tree unfiltered: rejected because it would preserve duplicate active Music source.
- Make Movies/TV own platform authentication: rejected because Portal must survive that module’s absence.
- Let Portal query application SQLite files: rejected because it breaks module ownership and failure isolation.
- Combine Portal and privileged infrastructure: rejected because it increases credential and mount exposure.

## Phase 0 boundary

This ADR changes documentation only. It does not rename a repository, import history, move source, alter Compose, create the Portal, publish images, change branches, migrate databases, or touch the NAS.
