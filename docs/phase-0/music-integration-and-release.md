# Music integration preservation and image release criteria

Status: Phase 0 contract  
Music_Downloader remains independently owned. This document does not authorize changes to it.

## Music-specific integrations currently present in Media_Downloader

The following behavior must be represented by a released Music image or an explicit Media-side integration contract before the copied music directory can be removed.

### Build and runtime

- Music backend build context and application package.
- fox-den-music-web and fox-den-music-worker commands.
- Non-root UID/GID build and runtime behavior.
- Read-only application filesystem, dropped capabilities, no-new-privileges, init process, tmpfs, memory limits, health checks, and stop grace periods.
- Music web restricted from the real library.
- Music worker as the only Music service with a writable /music bind.

### Persistent state and mounts

- /config and foxden-music.db ownership.
- /staging job workspace and upload temporary directory.
- /downloads completed-download inbox.
- /music final library and /music/.imports atomic-publication workspace.
- Browser /config profile and /downloads handoff.
- The requirement that config is suitable for local SQLite locking and that atomic Music publication remains on one compatible filesystem.

### Environment contract

- Application environment, logging, umask, upload and archive safety limits.
- ffprobe and ffmpeg paths and timeouts.
- MusicBrainz, Cover Art Archive, matching thresholds, artwork limits, and metadata caching.
- acquisition/provider and request-workflow settings.
- download inbox settling, size, recursion, move, and auto-import behavior.
- browser home, route, profile, UID/GID, timezone, and kiosk behavior.
- Music library scanning, storage snapshots, polling, heartbeat, and inventory batching.
- Jellyfin URL, API key or key file, and timeout.
- CSRF secret or secret file.
- Optional Spotify, Chromaprint, and AcoustID configuration when supported by the selected Music release.

### Gateway and user interface

- Root gateway route to Music web.
- /server-browser same-origin route and websocket forwarding.
- Long upload/download timeouts and disabled proxy request buffering.
- Media-session protection in Full mode without requiring Media authentication in Music Only mode.
- Relative application links that work behind the gateway and supported reverse proxies.
- Browser handoff and download-inbox behavior used from desktop and mobile.

### Tests, tools, and documentation

- Music regression tests currently executed from the Media CI suite.
- Compose topology and release-version checks.
- Container smoke tests for non-root web and worker processes.
- Gateway and browser route smoke tests.
- Music environment documentation and migration guidance.
- Compatibility for current service names where scripts or operational documentation depend on them.

### Security and functional invariants

- secure archive validation;
- readable-audio and metadata validation;
- no direct unvalidated writes to the final library;
- no-overwrite duplicate handling;
- atomic publication;
- existing import history and schema migration;
- retryable Jellyfin failure after successful import;
- incomplete browser downloads and partial files rejected;
- browser isolation and visible human handling of logins, consent, CAPTCHA, and selection.

Removal gate: the copied tree remains until all items above are mapped to a released artifact or Media-owned contract and Full integration tests pass.

## Acceptance criteria for a released Music image

### Source and version

- Built by Music_Downloader CI from an exact reviewed release commit.
- Semantic version agrees across package metadata, runtime API, release notes, and image tag.
- The source tag is immutable.
- OCI labels record source repository, commit, version, creation time, and license information where available.
- Published image digest is recorded in release output.
- Media pins the digest; latest is not used for a stable integration.

### CI and security

- Validation, regression tests, packaging, container smoke, supported Python release tests, browser tests, and the main release gate all pass.
- The existing dependency vulnerability audit failure is resolved. The audit job must pass against the final locked/resolved runtime dependencies; skipping it or allowing the main gate to remain red is not acceptance.
- Any dependency change made to resolve the audit receives regression coverage and release-note attribution.
- A container vulnerability scan reports no unapproved critical vulnerabilities. Severity policy and any time-limited exception require an explicit recorded decision.
- The image contains no repository credential, populated environment file, provider secret, API key, browser profile, media file, or developer-specific path.
- Software-bill-of-materials and provenance/signature policy is decided and then enforced consistently.

### Runtime isolation

- Web and worker start as the configured non-root UID/GID.
- Application containers remain read-only apart from declared mounts and tmpfs.
- Web has no writable real Music mount.
- Worker has only the Music mounts and secrets it requires.
- Neither service receives Docker socket, privileged mode, host networking, devices, or unnecessary capabilities.
- Health checks fail clearly for unreadable config, staging, heartbeat, database, or Music mounts without exposing secrets.

### Database and upgrade safety

- Fresh database initialization passes.
- Supported schema-2 to schema-3 migration is tested on a representative copy.
- Migration is serialized when web and worker start together.
- Existing jobs, acquisition history, import history, candidates, duplicate ledger, and inventory survive.
- Unsupported future/older schemas fail before job claiming or library writes.
- Release notes state backup, forward-migration, and rollback requirements.
- No release test writes to production data.

### Configuration contract

- The image accepts the documented existing Music variables required for migration.
- Direct-value and file-based secret behavior is documented.
- Missing optional integrations leave them disabled.
- Invalid URLs, ports, credentials-file paths, permissions, and overlapping storage layouts produce actionable redacted errors.
- No qBittorrent, Gluetun, Media, Movies, or TV setting is required to start Music.
- Environment overrides are exercised by CI.
- The image works without source-code or Compose editing in the supported Music Only example.

### Functional verification

Automated tests must cover:

- direct upload and server inbox;
- single-track and complete-release imports;
- ambiguous/low-confidence review;
- archive protections and unexpected file rejection;
- tagging, year, recording/release identifiers, and track-total behavior;
- duplicates and existing-destination refusal;
- atomic publish and interrupted-job recovery;
- library scan and history;
- browser-disabled operation;
- optional browser route when enabled;
- Jellyfin-disabled operation and a mocked refresh path.

Manual release evidence must clearly separate:

- CI-validated behavior;
- local container validation;
- real-provider validation;
- real Jellyfin validation;
- NAS deployment validation.

A real NAS/provider/Jellyfin test may remain a post-publication acceptance activity, but the image must not be described as live-verified until that test occurs.

## Media consumption gate

Before Media changes from bundled source to the released image:

1. Record Music version, digest, commit, schema range, and configuration-contract revision.
2. Run Music Only acceptance against the image.
3. Run Full mode integration tests using the image, not a local Music build context.
4. Confirm gateway auth, browser, upload, worker health, library mounts, and Jellyfin configuration.
5. Confirm existing Media environment variables either remain accepted or have a tested compatibility mapping.
6. Keep the bundled source available for rollback until the image-based stack passes a shadow rehearsal.
7. Obtain explicit approval for source-tree removal and deployment migration.
