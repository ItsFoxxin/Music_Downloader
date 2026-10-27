# Phase 1B integration notes

Status: in progress on Fox Den Media 0.4.1

## First integration slice

Movies/TV now implements the versioned `GET /api/platform/v1/summary` contract.
The endpoint reports only:

- module ID, name, and release version;
- worker health with a bounded generic summary;
- boolean availability for requests, library, acquisition, and browser features.

It does not query request, job, import, torrent, or library records. Activity is
an empty list until authenticated Portal-to-module requests are implemented.
Tests create deliberately private records and prove that titles, source URLs,
magnet data, tracker tokens, host paths, and application credentials are absent.

This keeps the initial endpoint no more sensitive than a conventional service
health/capability response while allowing the real Movies/TV process to validate
against Portal contract v1.

## Approved ingress direction

ADR 0003 records that the existing Nginx gateway becomes the sole Fox Den ingress
while Portal remains an independent container. The review configuration makes
Portal the platform root and session authority, uses deferred optional upstreams,
strips client identity headers, preserves upload/WebSocket proxy behavior, and
returns a generic 503 for unavailable modules.

The remaining approval boundary is the integrity-protected Portal-to-module
identity assertion, role propagation, and which activity fields may cross that
authenticated boundary.

Production Compose and the active gateway configuration remain unchanged during
this review slice. No NAS state, Music source, or application database migration
is changed.
