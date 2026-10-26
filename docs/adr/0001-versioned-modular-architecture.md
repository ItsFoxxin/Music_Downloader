# ADR 0001: Versioned modular Fox Den architecture

- Status: Accepted; implementation pending
- Decision date: 2026-10-26
- Scope: Repository ownership, service boundaries, releases, deployment modes, and portable configuration
- Supersedes: No prior ADR
- Approved option: Option C with contract-only Option D

## Context

Media_Downloader currently contains the Movies/TV application, integrated gateway, browser, Music web and worker services, qBittorrent, and Gluetun. Its development branch also contains a copied Music source tree. Music_Downloader separately owns the standalone Music application and is advancing independently.

The copied and standalone Music trees have already diverged. Applying security, schema, user-interface, and workflow fixes to two source trees is not sustainable. At the same time, Music must remain independently deployable and the integrated Media deployment must remain one coherent product.

Fox Den also needs to install cleanly on ordinary Linux Docker hosts and NAS systems without embedding a particular NAS path, address, domain, account, or credential. Operators should select a deployment mode and configure that mode through documented environment files instead of editing source or Compose YAML.

## Decision

### Repository responsibilities

Music_Downloader is authoritative for:

- Music web and worker source;
- Music database schema and migrations;
- music acquisition, validation, tagging, atomic publishing, duplicate handling, library inventory, and Jellyfin refresh;
- the standalone Music deployment contract;
- Music release notes, tests, packages, and versioned container images.

Media_Downloader is authoritative for:

- Movies/TV source and its database;
- the integrated Fox Den gateway and authentication composition;
- deployment-mode manifests and examples;
- optional contained-browser composition;
- optional managed qBittorrent and Gluetun composition;
- the cross-product compatibility matrix, full-stack tests, migration documentation, and integrated release.

Media_Downloader will consume a released Music image. It will not read or write the Music database directly. Music_Downloader will not depend on Media_Downloader source.

### Contract-only shared layer

Shared behavior is expressed through versioned contracts:

- HTTP routes, health responses, and capability discovery;
- gateway and forwarded-header expectations;
- authentication/session boundaries;
- browser handoff paths;
- container mount and ownership contracts;
- environment-variable names, meanings, defaults, and deprecation periods;
- compatible component and database-schema ranges.

A shared code package or third repository is not approved. It may be proposed later only when at least two independent consumers need the same stable implementation and ownership is clear.

### Versioning and artifact policy

- Music uses semantic versions and publishes an immutable image from an exact standalone Music commit and release tag.
- Integrated Media releases pin the Music image by immutable digest. A human-readable version tag may accompany the digest but must not be the sole production pin.
- Media maintains a compatibility record containing Media version, Music version and digest, supported Music schema range, gateway revision, browser image, qBittorrent API range, and Gluetun image.
- Moving tags such as latest are not acceptable in a reproducible release.
- Stable promotion requires the component acceptance criteria and the relevant deployment-mode acceptance tests.
- Development builds remain clearly marked and must not be represented as stable or NAS-verified.
- Database schema versions are independent from application and API versions.
- Rollback compatibility must be stated for every schema-changing release.

### Modular deployment

The target offers explicit, documented entrypoints for:

- Music Only;
- Movies/TV Only with an external qBittorrent service;
- Movies/TV with managed qBittorrent and optional Gluetun;
- Full Media with external qBittorrent;
- Full Managed with Music, Movies/TV, browser, qBittorrent, and Gluetun.

Separate Compose entrypoints or overlays are preferred over a single file in which inactive services still interpolate required variables. Profiles may be used only where they do not make disabled-service configuration mandatory or obscure the effective topology.

Each mode has a minimal environment example. Optional modules fail independently and must not prevent unrelated enabled services from starting.

### Portable environment-driven configuration

Deployment-specific behavior is configured through documented environment variables and secret files. Users should not need to edit application source or Compose files for supported deployment layouts.

The public configuration surface covers, where relevant to the selected mode:

- host paths for Music, Movies, TV, downloads, staging, databases/config, and browser profiles;
- UID, GID, umask, timezone, and ownership expectations;
- bind addresses, ports, public URLs, proxy hostnames, HTTPS and secure-cookie behavior;
- Jellyfin connection and enablement;
- MusicBrainz and supported metadata providers;
- qBittorrent internal/public URLs, credentials, Web UI port, and container-side download-root mapping;
- external versus managed qBittorrent;
- optional Gluetun/VPN settings;
- contained-browser enablement, profile path, bind policy, home URL, and acquisition behavior;
- authentication secrets and supported secret-file forms;
- documented resource limits, timeouts, polling, and safety limits that provide an operator benefit.

Internal implementation details are not automatically exposed. A variable is public only when operators have a credible need, it can be validated safely, and its compatibility can be maintained.

No example may contain a personal NAS path, LAN IP, domain, username, or populated credential.

### Module-scoped configuration

- Music Only does not require qBittorrent, Gluetun, Movies/TV, or VPN variables.
- Movies/TV Only does not require Music paths, MusicBrainz, Spotify, AcoustID, or Music worker variables.
- External qBittorrent does not require Gluetun or WireGuard variables.
- Jellyfin-disabled deployments do not require a URL or key.
- Browser-disabled deployments do not require a browser profile, port, or acquisition provider URL.
- Managed VPN configuration is validated only when that module is enabled.
- Required-variable interpolation must be isolated to the Compose file or service that uses the variable.

Recommended documentation layout:

- .env.example as a safe full catalog;
- env/music.example;
- env/media.example;
- env/full.example;
- env/qbittorrent-external.example;
- env/torrent-managed.example;
- env/migration-existing.example.

The exact filenames remain an implementation decision, but the mode-scoped behavior is part of this ADR.

### Defaults and validation

Defaults must be secure and beginner-appropriate:

- bind user-facing services to loopback unless explicit LAN exposure is selected;
- do not expose qBittorrent or the browser independently in the full gateway mode;
- disable automatic import unless the application release explicitly documents otherwise;
- disable optional integrations when their enable flag or complete configuration is absent;
- use non-root application users, dropped capabilities, read-only filesystems, and no-new-privileges where currently supported;
- prevent automatic root-owned bind-directory creation;
- never log secret values.

A future preflight command validates only the selected mode and reports:

- missing required variables;
- invalid URLs, ports, bind addresses, booleans, IDs, and file modes;
- nonexistent or inaccessible bind directories;
- read/write and ownership problems;
- overlapping config, staging, download, and library paths;
- storage layouts incompatible with atomic same-filesystem publication;
- incomplete optional-service combinations;
- inconsistent qBittorrent container-side path mappings;
- unsafe public exposure and HTTPS/cookie mismatches.

Every error must name the setting or path, explain the expected condition, and suggest a corrective action without printing credentials.

### Platform scope

The supported design target is Linux Docker Engine with Docker Compose on:

- Ubuntu and Debian;
- general-purpose Linux Docker hosts;
- NAS products that provide sufficiently compatible Docker Compose and bind mounts;
- hosts using an existing reverse proxy.

Support is conditional on real platform capabilities. Atomic no-replace publication, local SQLite locking, bind ownership, Linux devices for VPN, and reverse-proxy websocket behavior must be documented as requirements. Network filesystems, vendor-modified Compose implementations, rootless device access, SELinux/AppArmor policy, and CPU architecture differences require explicit testing rather than a universal-compatibility claim.

The architecture is not tied to UGREEN-specific paths or behavior.

### Data ownership

- Music alone owns its SQLite database, staging jobs, download inbox processing, and final Music library mutation.
- Media alone owns media.db, torrent validation records, Movies/TV staging, and final Movies/TV library mutation.
- qBittorrent alone owns its appdata and torrent resume state.
- Gluetun alone owns VPN runtime configuration.
- Jellyfin is an external integration and remains authoritative for its own database.
- Gateway and browser processes receive only the mounts and secrets they need.
- Old and new services must never write concurrently to the same database, appdata, staging area, inbox, or library.

## Consequences

Benefits:

- one authoritative Music source and release;
- independent Music and Media development;
- reproducible integrated releases;
- smaller migration blast radius;
- deployable modes that do not require irrelevant configuration;
- portable examples for beginners and advanced operators;
- explicit compatibility and rollback information.

Costs:

- Media integration releases depend on a successfully published Music artifact;
- cross-repository compatibility testing and release coordination are required;
- gateway configurations must vary safely by deployment mode;
- environment variables become a maintained public API;
- the copied Music tree can be removed only after contract and integration gates pass.

## Rejected alternatives

- Continue duplicated Music source: rejected because drift is already measurable.
- Immediate monorepo: rejected because it disrupts independent Music releases and active work.
- Broad shared library now: rejected because shared business logic and ownership are not mature.
- One mandatory seven-service Compose file: rejected because inactive modules currently impose unrelated configuration.
- Direct cross-module SQLite access: rejected because it defeats isolation, migration ownership, and independent deployment.

## Non-goals for Phase 0

This ADR does not implement a preflight command, publish an image, modify Compose, change authentication, remove copied code, migrate state, or deploy anything.
