# Phase 1 and Phase 2 proposed implementation plan

Status: Review required before implementation

## Phase 1: establish the authoritative Music artifact contract

Phase 1 does not take over the independent Music bug-fix task.

### Music-owned prerequisite

The independent Music work delivers a release candidate that:

- resolves the current dependency audit failure;
- passes all Music release acceptance criteria;
- publishes a semantic version, immutable image digest, release notes, schema range, and environment contract;
- documents CI-validated versus real-environment-unverified behavior.

Media work waits for that artifact rather than editing Music source.

### Media-owned work

1. Add a machine-readable compatibility manifest schema.
2. Record the candidate Music version, digest, commit, schema range, and required environment-contract revision.
3. Add read-only CI verification that:
   - the image metadata matches the declared release;
   - the image is pinned immutably;
   - non-root web and worker commands start;
   - health checks and declared mount ownership match the contract.
4. Create Music Only and Full integration fixtures that use the published image while retaining the bundled source path as rollback.
5. Map every item in the Music integration-preservation document to automated evidence or an explicitly manual check.
6. Produce an updated removal-readiness report.

### Phase 1 exclusions

- no bundled-source removal;
- no production database migration;
- no NAS deployment;
- no replacement of the currently running Music image;
- no Compose mode rollout to production.

### Phase 1 exit gate

- authoritative Music release is green and published;
- dependency audit passes;
- Media verifies the image by digest;
- Music Only and provisional Full image-based tests pass;
- rollback to the bundled development path remains possible;
- user reviews evidence and approves Phase 2.

## Phase 2: implement modular portable deployment

### Work package 1: configuration contract

- Define versioned public variables by module.
- Preserve existing variable names during the migration window.
- Add consistent secret-file support.
- Create safe full catalog plus Music, Media, Full, external-qBittorrent, managed-torrent, and migration examples.
- Document precedence, defaults, enable flags, deprecations, and redaction rules.
- Keep internal settings internal unless an operator benefit is demonstrated.

### Work package 2: deployment entrypoints

- Add explicit Music Only, Movies/TV Only, Full, and managed-torrent Compose entrypoints/overlays.
- Ensure disabled modules do not interpolate required variables.
- Replace moving tags with reviewed release pins in stable manifests.
- Preserve current service isolation, capabilities, read-only filesystems, and mount minimality.
- Support external qBittorrent without Gluetun.
- Make browser and Jellyfin independently optional.

### Work package 3: gateway modes

- Provide mode-specific route configuration.
- Remove Music Only dependency on Media session checks.
- Preserve shared authentication for Full mode according to the approved auth decision.
- Validate reverse-proxy base URLs, forwarded headers, HTTPS, secure cookies, upload limits, and browser websockets.
- Default to no independent browser or qBittorrent exposure.

### Work package 4: preflight

- Implement a mode-aware, redacting preflight command.
- Check values, directories, ownership/access, overlaps, atomic-publication layout, qBittorrent path mapping, optional dependencies, and exposure.
- Provide corrective error messages without secrets.
- Run preflight in CI and document it as the first deployment step.

### Work package 5: CI and documentation

- Implement every deployment-mode and portability criterion.
- Add compatibility tests for existing variables.
- Add beginner quick starts and advanced examples.
- Add migration example without performing a migration.
- Record exact evidence boundaries.

### Work package 6: remove copied Music source

This is last, not first.

- Require all Phase 1 and Phase 2 tests to pass using the image.
- Confirm no build, test, script, gateway, browser, documentation, or migration dependency remains on the copied tree.
- Preserve a tagged pre-removal Media revision.
- Remove the tree in one reviewable change.
- Do not deploy or migrate the NAS without a separate cutover approval.

## Proposed validation order

1. Static configuration and secret scan.
2. Mode-specific Compose render.
3. Preflight positive and negative fixtures.
4. Music and Media unit tests.
5. Published-image contract tests.
6. Mode-specific container smoke.
7. Gateway/auth/browser integration.
8. Filesystem and interrupted-state integration.
9. Package and compatibility manifest publication.
10. Optional shadow environment rehearsal after separate approval.

## Remaining decisions requiring approval

| Decision | Recommended default | Why it matters |
| --- | --- | --- |
| Music container registry visibility | Public GHCR unless licensing/privacy requires private | Determines authentication and beginner deployment complexity |
| CPU architectures | amd64 required; add arm64 only after native CI/runtime evidence | Avoids claiming unsupported NAS hardware |
| Authentication owner | Gateway/shared Media session for Full; standalone auth boundary for single-module modes | Removes current mandatory Media dependency without weakening Full mode |
| Reverse-proxy trust | Explicit trusted proxy list; do not trust arbitrary forwarded headers | Prevents spoofed HTTPS/client identity |
| qBittorrent default | External for existing-install migration; managed overlay for fresh installs | Minimizes disruption and preserves seeding/appdata |
| Browser layout | One shared browser in Full mode, optional in each module; revisit dedicated profiles if conflicts appear | Minimizes containers while preserving isolation |
| Browser exposure | Gateway-only by default | Reduces attack surface |
| Jellyfin | Disabled unless both URL and secret are configured or an explicit enable flag is set | Makes no-Jellyfin mode predictable |
| Secret migration | Add file forms first; retain direct values for one documented compatibility cycle | Supports existing installations safely |
| Environment example filenames | Use module-scoped env directory plus root safe catalog | Beginner clarity and advanced composition |
| Stable image pinning | Digest plus semantic version in compatibility manifest | Reproducibility and readable operations |
| Vulnerability policy | No unresolved critical; dependency audit must pass; any lower-severity exception is documented and expires | Defines an objective release gate |
| SBOM/signing | Generate SBOM in Phase 1; sign images if GHCR workflow support is approved | Supply-chain evidence versus workflow complexity |
| Movies and TV paths | Expose separate MOVIES_PATH and TV_PATH or document a single MEDIA_PATH with fixed subdirectories | Affects portable storage layouts |
| Base URL/path-prefix support | Support host-based proxy first; approve path-prefix support only with dedicated tests | Path-prefix behavior adds gateway and frontend complexity |
| Resource limits | Document secure defaults with environment overrides for major services | NAS variability without exposing every internal knob |
| Configuration contract versioning | Publish a simple integer contract revision with every component | Enables compatibility checks independent of app semver |
| Database migration execution | Dedicated one-shot migration/preflight step before workers | Avoids multiple writers racing at startup |
| Media worker split | Defer until after modular deployment unless reliability testing shows need | Limits Phase 2 scope |
| Stable branch policy | Keep Media main stable and implement through dev/PR; separately resolve Music default-branch policy | Prevents architecture work from changing release governance implicitly |

No Phase 1 or Phase 2 item is authorized by this plan. Approval should identify any recommended default that must change.
