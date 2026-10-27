# Portal foundation architecture

Status: Phase 1A implementation; mocked modules only

## Outcome

Portal is an independent FastAPI application under portal/. It owns the unified
homepage, local accounts, sessions, optional OIDC login, module registry, module
health/capability/activity aggregation, and versioned platform contracts.

It is deliberately not wired into production Compose or the current gateway.

## Persistent state decision

Portal uses its own SQLite database because these security properties require
durable state:

- local users and Argon2id password hashes;
- one-time bootstrap use and expiration;
- opaque session hashes and immediate revocation;
- persistent login throttling;
- one-use OIDC state, nonce, and PKCE verifier records;
- stable OIDC subject-to-local-user mappings.

In-memory state would allow bootstrap reuse, lose accounts on restart, weaken
session invalidation, and reset rate limits. Browser cookies alone would prevent
server-side revocation.

The database defaults to /config/portal.db and must be on storage with reliable
SQLite locking. Portal never opens or mounts Music or Movies/TV databases.

## Module contract

Enabled modules are configured through PORTAL_MODULES_JSON. Portal requests only:

    GET /api/platform/v1/summary

Contract version 1.0 contains module ID/name/version, sanitized health, bounded
capabilities, and bounded recent activity. It forbids extra fields and does not
permit secrets, host paths, tracker data, stack traces, or raw database records.

Portal translates failures into four user-visible states:

- disabled: configured off and hidden;
- offline: connection failure, timeout, or unavailable response;
- unhealthy: valid module response reporting an issue, or invalid contract data;
- healthy: valid healthy response.

Calls use a bounded configurable timeout, response-size bound, strict schema,
parallel failure isolation, and safe generic errors. One module cannot crash or
delay the platform beyond its timeout.

## Authentication modes

- local: default, no external identity provider required;
- oidc: external OIDC only, with an administrator group required;
- hybrid: local and OIDC, suitable for Authentik plus a restricted emergency admin.

Local first-run setup requires a 32-character bootstrap secret from an environment
variable or secret file. The setup window is stored and expires. The first claim
uses a serialized database transaction, consumes the bootstrap state, and disables
public registration.

Passwords use Argon2id. Sessions are opaque random tokens; only SHA-256 hashes are
stored. Session cookies are HttpOnly, SameSite Strict, bounded, and Secure by
default for HTTPS. Authenticated mutations require a per-session CSRF token.
Login throttling persists without storing raw passwords or tokens.

Administrators can create local users and reset passwords. Reset revokes every
session for the target account. Offline recovery uses an interactive prompt or a
protected password file through foxden-portal-admin; no recovery credential is
printed by the web application.

## OIDC

OIDC uses authorization code, PKCE S256, state, nonce, discovery, exact issuer and
audience checks, token expiration, and JWKS signature validation. Only RS256 and
ES256 ID tokens are accepted. Access and ID tokens are not persisted.

The stable pair of provider issuer and subject maps to a local Portal identity.
Optional allowed groups deny unauthorized identities. Optional administrator
groups determine the initial Portal role.

After OIDC succeeds, Portal creates its own bounded local session. If the provider
later becomes unavailable, new OIDC logins fail safely, local login remains
available in hybrid mode, and existing Portal sessions continue until expiration
or revocation. Portal health and local pages remain available.

## Internal identity

Phase 1A defines but does not connect the internal identity contract. Short-lived,
audience-bound assertions include issuer, local subject, username, roles, times,
and a unique ID. Verification rejects malformed, expired, wrong-audience,
wrong-issuer, and untrusted signatures.

The public Portal rejects client-supplied X-FoxDen-Identity. A future ingress must
strip that header from all clients before obtaining a new assertion from a trusted
platform path. No browser endpoint issues assertions in Phase 1A.

## Container boundary

The Portal image runs as an unprivileged user. CI starts it with a read-only root,
all capabilities dropped, no-new-privileges, bounded tmpfs, and a writable Portal
config tmpfs. It receives no media mounts, application databases, browser profile,
Docker socket, qBittorrent credentials, or VPN device.
