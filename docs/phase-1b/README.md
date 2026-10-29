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

The Movies/TV frontend detects Portal assertions through the versioned session
response. Integrated sessions skip the legacy access-token prompt, expose stable
Portal and `/music/` navigation, and submit logout through Portal's existing
CSRF-protected form. Standalone sessions retain the access-token login, legacy
cookie, and workspace-lock behavior.

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
Restricted users have read access; Portal-originated writes require `admin` and
an exact configured browser `Origin`. Music additionally retains its existing
signed form-CSRF token checks. Nginx's private session subrequest supplies a
separate high-entropy ingress credential; `X-FoxDen-Ingress: 1` alone is never
treated as proof of a trusted caller.

Portal activity aggregation uses a separate service assertion scoped only to
`activity:read`. It is not an interactive user assertion, OIDC token, session
cookie, or proof that any Docker-network caller is trusted.

The authoritative Music integration is developed on a separate branch based on
recorded `Music_Downloader/dev` commit
`b4bbffbb2a739a8b78ec6b194416b8d4fb5e09ea`. The approved integration revision
is `478c1a6fe082aecd338fe81954b7946f02cbd007`. The local runner rejects any
other Music `HEAD` by default; `--music-commit` is reserved for an explicitly
approved replacement release. Music verifies Portal public JWKs, keeps
standalone behavior available when integration is disabled, supports the
`/music/` module prefix, and exposes only a service-authenticated sanitized
activity feed.

`integration/compose.yaml` is explicitly disposable. It builds Music from the
operator-supplied authoritative checkout, publishes only Nginx on loopback, and
uses project-specific named volumes for synthetic state. It contains no NAS
paths, production databases, qBittorrent, VPN, or production credentials.

```sh
python scripts/integration_stack.py up --music-source ../Music_Downloader --port 18080
python scripts/integration_stack.py down
```

The `down` action removes only the `foxden-media-integration` containers,
networks, named volumes, and generated test secrets. Production Compose and the
active gateway configuration remain unchanged. No NAS state or application
database migration is changed, and the review ingress must not replace existing
production routing before the next approval gate.
