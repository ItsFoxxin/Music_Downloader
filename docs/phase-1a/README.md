# Phase 1A review guide

## Delivered milestone

Portal `0.1.0` is the first independently runnable platform component for the
planned Fox Den Media modular monorepo. It provides:

- a responsive dashboard and shared platform navigation;
- environment-configured module registration and isolated status collection;
- local, OIDC-only, and hybrid authentication modes;
- a protected first-run administrator flow and Portal-owned SQLite state;
- mocked Music and Movies/TV adapters;
- language-neutral module contract v1 and a tested internal identity contract;
- a non-root image designed for a read-only container;
- layered CI additions without altering production Compose.

This phase does **not** consolidate repositories, copy newer Music source, wire a
real module, change the gateway, modify production Compose, deploy anything, or
read any NAS state.

## Review map

- `portal-architecture.md`: boundaries and persistence decisions;
- `auth-threat-model.md`: threats, controls, and residual risks;
- `authentik-oidc-setup.md`: exact pre-live Authentik and Caddy plan;
- `demo.md`: isolated mocked-service demonstration;
- `../../contracts/v1`: versioned interoperable contracts.

## Decisions still requiring approval

1. Whether Phase 1B should use a dedicated ingress container or extend the
   existing gateway process while retaining a separate Portal process.
2. Whether internal identity moves from the Phase 1A shared-secret HS256 contract
   to asymmetric signing before the first real module integration.
3. Whether OIDC group changes update an existing local role automatically or
   require explicit Portal-administrator approval.
4. The canonical same-origin routes (`/music/` and `/media/` are the current
   proposal) and external hostname used for live redirect URIs.
5. Session lifetime, emergency-local-admin policy, and whether provider logout is
   required or local logout remains the default.
6. Which module is integrated first in Phase 1B. Movies/TV is the safer choice
   while independent work continues in `Music_Downloader/dev`.

## Proposed Phase 1B after approval

1. Add a dedicated development-only Compose overlay for Portal and mock modules.
2. Implement one real module-summary endpoint, preferably Movies/TV first.
3. Add a trusted ingress assertion exchange, header stripping, and end-to-end
   spoofing tests; keep ingress and Portal as distinct trust boundaries.
4. Exercise a mock OIDC provider in container CI and validate restart persistence.
5. Add backup/restore and key-rotation runbooks for Portal-owned state.
6. Test the approved reverse-proxy routes without touching production Compose.

Phase 1B exits only when Portal remains available during module failure, real
module status obeys contract v1, authentication cannot be bypassed at ingress,
and each approved deployment mode starts independently in CI.

## Proposed Phase 2 after approval

1. Freeze source ownership and import the authoritative
   `Music_Downloader/dev` history without using the obsolete bundled copy.
2. Preserve Movies/TV, gateway, browser, qBittorrent/VPN, and infrastructure
   ownership from Media Downloader according to the approved consolidation map.
3. Introduce modular Compose profiles and environment examples for Music Only,
   Movies/TV Only, Full External Torrent, and Full Managed.
4. Run database/configuration compatibility checks and a dry-run migration using
   copies only; never allow old and new writers to share live state.
5. Validate backup, cutover, and rollback gates before any repository rename,
   production deployment, database migration, or NAS change.

Phase 2 must remain blocked until current Music release work is complete and a
specific consolidation/cutover plan is separately approved.
