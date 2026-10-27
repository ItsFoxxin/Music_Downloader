# Fox Den Media platform contracts v1

Phase 1A defines contracts without connecting either production module.

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

## Internal identity assertion

`X-FoxDen-Identity` is reserved for a later trusted ingress-to-module exchange.
The v1 assertion has an exact HS256 header and these exact claims:

- `iss`: configured Fox Den assertion issuer;
- `aud`: one module ID;
- `sub`: stable Portal-local user ID;
- `preferred_username`: display-safe local username;
- `roles`: bounded Portal roles;
- `iat`, `nbf`, `exp`: issued/not-before/expiry timestamps;
- `jti`: unique assertion identifier.

Assertions expire within five minutes; the Phase 1A issuer defaults to 60 seconds.
Modules must verify signature, issuer, exact audience, lifetime, and exact claim
shape. Public clients cannot supply this header: Portal rejects it now, and the
future ingress must strip it before issuing a new trusted assertion.

Phase 1A provides issue/verify library functions and adversarial tests only. It
does not expose an assertion endpoint or connect the contract to a module.
