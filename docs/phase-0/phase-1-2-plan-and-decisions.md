# Revised Phase 1 and Phase 2 implementation plan

Status: Review required before implementation  
Architecture: Modular monorepo with independent Portal

## First safe implementation alongside current Music work

Phase 1A is the first safe implementation phase:

- work only in Media_Downloader on a dedicated feature branch;
- create a new apps/portal foundation and contracts schemas;
- use mock Music and Movies/TV module adapters;
- add Portal unit, security, degraded-state, and contract tests;
- do not connect Portal to current Compose, gateway, databases, or NAS;
- do not change, copy, move, or merge Music_Downloader;
- keep Portal free of module databases, libraries, torrent appdata, VPN secrets, and browser profiles.

This work can later be imported as part of Media unique history. It does not conflict with Music bug fixes because it consumes only proposed contracts and mocks.

Phase 1A requires approval before implementation.

## Phase 1: independent foundations

### Phase 1A: Portal and contracts

1. Finalize versioned capability, health, activity, navigation, and identity-assertion schemas.
2. Implement Portal configuration, module registry, homepage, login/session, health aggregation, combined activity, and degraded-state UI against mocks.
3. Add bounded timeouts, sanitized errors, and contract-version handling.
4. Add a minimal Portal container with non-root/read-only hardening.
5. Add tests proving zero-module startup and module failure isolation.
6. Do not alter production Compose.

### Phase 1B: consolidation rehearsal

1. Inventory branches, tags, releases, PRs, Actions, settings, packages, and links in both repositories.
2. Create and verify bare mirrors.
3. Build a temporary filtered Media history excluding music and all state/secrets.
4. Produce source-to-filtered commit mapping.
5. Rehearse Music path moves and unrelated-history merge in disposable repositories.
6. Generate collision, provenance, size, secret, and test reports.
7. Do not rename or merge the real repositories.

### Independent Music prerequisite

The separate Music task must:

- finish its bug fixes;
- resolve dependency audit failure;
- pass its release gates;
- identify an authoritative commit, schema, configuration contract, and rollback boundary.

Portal/contracts work may proceed without waiting. Real source consolidation may not.

### Phase 1 exit

- Portal mock implementation and security tests pass;
- contracts reviewed by Music and Media owners;
- filtered-history rehearsal proves obsolete music exclusion;
- repository rename impact inventory complete;
- independent Music checkpoint green;
- user approves Phase 2.

## Phase 2: canonical monorepo bootstrap

### Work package 1: create bootstrap branch

- Start from approved authoritative Music commit.
- Create monorepo/bootstrap.
- Move Music source under apps/music with history-preserving moves.
- Keep database format and runtime behavior unchanged.

### Work package 2: import unique Media history

- Merge the reviewed filtered history under collision-free namespace.
- Move Movies/TV to apps/media.
- Move approved Portal/contracts work to canonical paths.
- Reconcile tests/docs/infrastructure using the source ownership map.
- Verify only one active Music implementation exists.

### Work package 3: Portal and ingress integration

- Add Music and Media contract endpoints.
- Make Portal authoritative for integrated auth.
- Make ingress use Portal auth without moving product logic into ingress.
- Validate signed/integrity-protected internal identity.
- Preserve independent failure behavior.

### Work package 4: modular deployment

- Add Music Only, Movies/TV external, Full external, and Full Managed compositions.
- Provide mode-scoped environment examples.
- Implement redacting mode-aware preflight.
- Preserve existing variable compatibility.
- Pin stable images and document platform limitations.
- Provide one simple Full Managed command.

### Work package 5: monorepo CI and releases

- Use path-aware module jobs for development.
- Require complete sequential platform gates for stable release.
- Test Portal contracts, every deployment mode, isolation, migrations on copies, packaging, and containers.
- Publish coordinated first-party images from one commit.
- Publish compatibility manifest, SBOM policy output, release notes, backup, and rollback guidance.

### Work package 6: repository rename

- Execute only after a successful dry run and explicit approval.
- Rename Music_Downloader to FoxDen_Media at the approved point.
- Update Actions/action references, remotes, badges, links, Pages, webhooks, packages, branch rules, environments, and documentation.
- Do not reuse the old name.
- Keep Media_Downloader available.

### Phase 2 exit

- canonical monorepo tests and all modes pass;
- Portal survives every module failure test;
- provenance report and repository settings audit pass;
- no production data touched;
- user reviews evidence before repository merge/promotion or NAS migration.

## Later phases, not authorized

- shadow deployment using copied state;
- database migration rehearsals;
- NAS cutover;
- old repository archival;
- Media worker split;
- production platform release.

## Decision register

| Decision | Recommended default | Approval state |
| --- | --- | --- |
| Canonical lineage | Rename Music_Downloader after its release checkpoint | Proposed |
| Final repository name | FoxDen_Media | Proposed |
| Rename timing | After bootstrap is reviewable and active Music PR is resolved | Proposed |
| Default branches | main stable, dev development; decide treatment of master during rehearsal | Unresolved |
| First platform version | New major platform version | Unresolved |
| Ingress/Portal split | Separate ingress and Portal containers | Proposed |
| Portal persistence | Separate portal.db only if sessions/activity need durable state | Unresolved |
| Internal identity | Signed short-lived assertion; exact mechanism threat-modeled in Phase 1 | Proposed |
| Full Managed count | Eight containers; keep Media worker internal initially | Proposed |
| Media worker split | Defer | Proposed |
| History import | Filter Media history, exclude music, preserve provenance map | Proposed |
| Original repositories | Retain until post-migration approval | Approved direction |
| Registry/image names | New Fox Den Media package names; do not assume automatic rename | Unresolved |
| Registry visibility | Public unless privacy/licensing requires private | Unresolved |
| CPU support | amd64 initially; arm64 only after CI/runtime evidence | Unresolved |
| qBittorrent migration default | External existing stack; managed option for fresh installs | Proposed |
| Browser | One optional shared browser, gateway-only by default | Proposed |
| Movies/TV paths | Separate configurable Movies and TV paths | Proposed |
| Proxy support | Host-based first; path-prefix only with dedicated tests | Proposed |
| Secret migration | Add file forms, retain direct values for one compatibility cycle | Proposed |
| Database migrations | Dedicated one-shot migration/preflight before workers | Proposed |
| SBOM/signing | SBOM required; signing decision pending | Unresolved |
| Vulnerability gate | Dependency audit green; no unapproved critical vulnerabilities | Proposed |
| Portal work location | Media feature branch for Phase 1A, later imported | Proposed |

No Phase 1 or Phase 2 work is authorized by this document.
