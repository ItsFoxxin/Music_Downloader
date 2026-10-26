# Phase 0 architecture package

Status: Accepted architecture; implementation pending  
Date: 2026-10-26  
Primary repository: ItsFoxxin/Media_Downloader

This package records the approved target architecture for Fox Den Media. It is documentation only. It does not change application code, Compose topology, databases, container images, or a live deployment.

## Approved direction

Fox Den Media uses Option C with contract-only Option D:

- Media_Downloader owns Movies/TV and the integrated deployment.
- Music_Downloader remains the authoritative, independently releasable Music application.
- The integrated deployment will consume a pinned, versioned Music image rather than maintain a copied Music source tree.
- Modules communicate through documented HTTP, health, authentication, mount, and configuration contracts. They never share application databases.
- Shared code will be introduced only when multiple independently owned consumers justify it.

## Documents

- ADR 0001: repository ownership, versioning, modular deployment, and portable configuration.
- Compatibility matrix: current and target component compatibility.
- Music integration contract: integrations that must survive removal of the bundled Music tree and Music image release gates.
- NAS inventory checklist: read-only data to collect before migration planning.
- Deployment acceptance: testable requirements for Music Only, Movies/TV Only, and Full Managed modes.
- Phase 1 and Phase 2 plan: proposed work packages and decisions still requiring approval.

## Phase boundary

Phase 0 permits documentation and analysis only. It expressly does not authorize:

- removing or updating bundled Music source;
- changing Compose services, profiles, networks, ports, mounts, or gateway routes;
- modifying Music_Downloader or its active bug-fix and release work;
- migrating or opening a production database with a newer application;
- modifying qBittorrent, Gluetun, Jellyfin, reverse proxy, NAS files, or a deployed container;
- publishing or deploying a replacement stack.

Phase 1 and Phase 2 require a separate approval after review of this package.
