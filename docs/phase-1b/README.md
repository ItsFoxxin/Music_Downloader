# Phase 1B integration notes

Status: in progress on Fox Den Media 0.4.1

## First integration slice

Movies/TV now implements the versioned `GET /api/platform/v1/summary` contract.
The endpoint reports only:

- module ID, name, and release version;
- worker health with a bounded generic summary;
- boolean availability for requests, library, acquisition, and browser features.

The public summary does not query request, job, import, torrent, or library
records. A separate service-authenticated activity endpoint emits bounded,
generic state transitions only. Tests create deliberately private records and
prove that titles, source URLs, magnet data, tracker tokens, host paths, and
application credentials are absent.

This keeps the initial endpoint no more sensitive than a conventional service
health/capability response while allowing the real Movies/TV process to validate
against Portal contract v1.

## Approved ingress direction

ADR 0003 records that the existing Nginx gateway becomes the sole Fox Den ingress
while Portal remains an independent container. The review configuration makes
Portal the platform root and session authority, uses deferred optional upstreams,
strips client identity headers, preserves upload/WebSocket proxy behavior, and
returns a generic 503 for unavailable modules.

## Approved internal identity

Portal is the only Ed25519 private-key holder. Nginx obtains a 30–60 second,
audience-bound assertion from a private session subrequest and forwards it only
to the intended module. Movies/TV independently validates the public key,
issuer, audience, use, scopes, times, token ID, signature, and replay state.
Restricted users have read access; Portal-originated writes require `admin`.

Portal activity aggregation uses a separate service assertion scoped only to
`activity:read`. It is not an interactive user assertion, OIDC token, session
cookie, or proof that any Docker-network caller is trusted.

Production Compose and the active gateway configuration remain unchanged during
this review slice. No NAS state, Music source, or application database migration
is changed. Music still needs its own contract-compatible verifier before the
review ingress can replace existing production routing.
