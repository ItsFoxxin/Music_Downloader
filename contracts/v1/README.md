# Fox Den Media platform contracts v1

Contract v1 is shared by Portal and independently protected modules.

## Module summary

An enabled module exposes `GET /api/platform/v1/summary` on its internal service
network. The response must validate against `module-summary.schema.json` and use
`contract_version: "1.0"`.

The endpoint is read-only and must return only presentation-safe status data. It
must never include credentials, tokens, host paths, download URLs, tracker data,
database rows, stack traces, or internal exception details. Portal rejects extra
fields, oversized responses, invalid paths, and unsupported contract versions.

Activity `path` values are same-origin application paths. Absolute URLs,
protocol-relative URLs, and parent traversal are forbidden.

The legacy `activity` member of a module summary remains present for v1 schema
compatibility but Portal does not display it. Integrated modules return an empty
list and use the separately authenticated activity endpoint below.

## Internal identity assertion

`X-FoxDen-Identity` carries a compact Ed25519-signed JWS from Portal to exactly
one module. Its protected header is exactly `alg: EdDSA`,
`typ: foxden-identity+jwt`, and a trusted `kid`. Its claims are exactly:

- `iss`: configured Fox Den assertion issuer;
- `aud`: one module ID;
- `sub`: stable Portal-local user ID;
- `preferred_username`: display-safe local username;
- `roles`: bounded Portal roles;
- `scope`: bounded internal permissions;
- `iat`, `nbf`, `exp`: issued/not-before/expiry timestamps;
- `jti`: unique assertion identifier.
- `token_use`: `user` or `service`.

Assertions live 30–60 seconds (45 by default). Modules verify the Ed25519
signature, trusted key ID, issuer, exact audience, use, scopes, timestamps,
unique token ID, and exact claim shape. A token consumed by one module cannot be
reused by another. Modules maintain bounded replay caches through expiration.

Nginx strips client-supplied identity headers. Its private Portal auth subrequest
receives an audience-bound assertion and forwards it only to that module; it
never mints or returns assertions to a browser. Authentik/OIDC tokens terminate
at Portal and are never reused as Fox Den internal assertions.

## Authenticated activity

`GET /api/platform/v1/activity` requires a distinct `token_use: service`
assertion with `activity:read` scope and the module's audience. It returns only
contract version, module ID, and up to 20 presentation-safe activity items.
User assertions cannot call it. Health reachability alone grants no activity
access. Request names, search inputs, download URLs, tracker data, credentials,
host paths, stack traces, and raw database records are forbidden.
