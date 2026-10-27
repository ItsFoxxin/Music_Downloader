# ADR 0003: Nginx ingress and independent Portal

- Status: Accepted for Fox Den Media 0.4.1
- Date: 2026-10-27

## Context

The existing Nginx gateway already owns same-origin routing, streaming upload
behavior, the contained browser WebSocket path, and the public application port.
Its authentication subrequest currently delegates to the Movies/TV session API,
which incorrectly makes one optional module the platform authentication authority.

Portal 0.1.0 now owns accounts, local/OIDC login, sessions, authorization, and
module aggregation. Portal must remain available when every module is absent.

## Decision

Refactor the existing Nginx gateway into the sole Fox Den ingress service. Keep
Portal as an independent process and container. Do not introduce another ingress
or replace Nginx without demonstrated need.

The future ingress layout is:

- `/` -> Portal;
- `/music/` -> Music when enabled and available;
- `/media/` -> Movies/TV when enabled and available;
- `/server-browser/` -> optional contained browser;
- an internal Nginx auth subrequest -> Portal session validation.

Variable upstream targets defer Docker DNS lookup, allowing ingress and Portal to
start without optional backends. Missing authenticated module routes return a
generic 503 and cannot make Portal unavailable.

Ingress strips `X-FoxDen-Identity` and Authentik identity headers from every
client request. It does not yet forward identity to modules. Authenticated
activity and single-sign-on module access remain blocked until an integrity-
protected, audience-bound Portal assertion is implemented and tested.

## Responsibility boundaries

- Ingress: routing, proxy headers, buffering, WebSocket upgrade, upload timeouts,
  authentication enforcement, and failure isolation.
- Portal: accounts, OIDC/local login, sessions, authorization, module registry,
  health aggregation, and dashboard.
- Modules: their own workflows, storage, databases, workers, and health.

Portal configuration uses an explicit public URL, so it does not derive security
decisions from untrusted forwarding headers. Caddy may terminate TLS and proxy to
ingress while preserving `Host`; secure cookies and OIDC redirects use the
configured HTTPS Portal public URL. Authentik headers never substitute for Portal
OIDC or signed internal identity.

## Migration safety

`gateway/nginx.conf` and production Compose remain unchanged during this review
slice. `gateway/portal-ingress.conf` is exercised in isolated CI with only Portal
running. Activation requires a later reviewed Compose migration, configured
secrets, backup/rollback notes, and live reverse-proxy validation.

## Consequences

- one ingress implementation and one public entry point;
- Portal availability is independent of Music, Movies/TV, browser, torrent, VPN,
  and Jellyfin availability;
- module paths fail closed when unauthenticated and fail safely when unavailable;
- activity remains empty until trusted module identity is complete;
- current production behavior is preserved until explicit cutover approval.
