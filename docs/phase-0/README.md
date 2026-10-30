# Phase 0 architecture package

Status: Revised architecture accepted; implementation pending  
Date: 2026-10-26  
Current primary planning repository: ItsFoxxin/Media_Downloader  
Target canonical repository: ItsFoxxin/FoxDen_Media

This package records the approved modular-monorepo direction. It is documentation only.

## Current decision

ADR 0002 supersedes ADR 0001:

- one canonical Fox Den Media repository;
- Music_Downloader dev is the authoritative Music foundation;
- unique Movies/TV, Portal, ingress, and infrastructure history comes from Media_Downloader dev;
- obsolete Media music source is excluded;
- Portal is independent of Music and Movies/TV availability;
- separate runtime processes, databases, workers, mounts, and security boundaries remain;
- modular environment-driven deployment modes remain mandatory.

## Documents

- ADR 0002: accepted monorepo, Portal, runtime, versioning, and portability decision.
- Compatibility matrix: present repository facts and target monorepo contracts.
- Repository consolidation strategy: rename and filtered-history approach, acceptance gates, and rollback.
- Source ownership map: canonical locations and responsibilities.
- Deployment architecture: Portal, ingress, modules, containers, networks, and modes.
- Music integration preservation: behavior that the move into apps/music must retain.
- NAS inventory checklist: read-only preparation; it remains unfilled.
- Deployment-mode acceptance: testable mode and Portal requirements.
- Phase 1/2 plan and decision register: proposed work only.

ADR 0001 is retained as superseded decision history.

## Phase boundary

This revision does not authorize:

- repository rename, transfer, archive, deletion, or history import;
- merging or closing the active Music pull request;
- changing default branches or branch protection;
- moving Music source or importing Media source;
- creating or wiring the Portal;
- changing Compose, images, ports, mounts, secrets, or authentication;
- database migration or NAS deployment.

Phase 1 and Phase 2 require separate approval.
