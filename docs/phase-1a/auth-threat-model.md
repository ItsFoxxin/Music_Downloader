# Portal authentication threat model

## Assets

- Portal accounts, roles, sessions, bootstrap status, and OIDC mappings;
- authorization to enter enabled modules;
- internal identity assertion key;
- OIDC client secret;
- integrity of module health/activity presentation.

## Trust boundaries

- browser to external reverse proxy/ingress;
- ingress to Portal;
- Portal to OIDC provider;
- Portal to module contract endpoints;
- trusted platform assertion issuer to modules;
- operator-controlled environment/secret files to Portal;
- Portal process to its own SQLite database.

## Principal threats and controls

### First-run account takeover

Control: no default account; long operator-provided bootstrap secret; short stored
setup window; constant-time comparison; one-use serialized claim; public setup
disabled after the first account; secrets never logged.

### Password theft and brute force

Control: Argon2id with explicit cost; generic login failures; persistent keyed
rate limits; secure form handling; password length/complexity policy; no password
logging; protected-file or interactive offline recovery.

### Session theft/fixation

Control: high-entropy opaque tokens, hash-only storage, fixed expiration, server
revocation, new token after authentication, HttpOnly/SameSite cookies, Secure on
HTTPS, CSRF tokens, no token in URLs.

### OIDC replay, substitution, or forged token

Control: one-use state; nonce; PKCE S256; strict redirect URI; issuer, audience,
expiration and signature checks; allowed algorithms; JWKS over HTTPS; short flow
expiry; no access-token trust as an ID token.

### Unauthorized OIDC group

Control: optional allow-list gate evaluated before local identity creation;
administrator mapping separate from general access; OIDC-only mode requires an
administrator group configuration.

### Identity-header spoofing

Control: public Portal rejects X-FoxDen-Identity. Future ingress must remove all
client-supplied identity headers. Modules accept only signed, short-lived,
audience-bound assertions from an isolated key, never Authentik forward-auth
headers directly.

### Compromised or offline module

Control: strict versioned schema; response-size and timeout bounds; generic errors;
escaped templates; no secret fields; module data never controls authentication;
module failure cannot disable Portal or another module.

### Compromised reverse proxy or forwarded headers

Control: Phase 1A derives no identity from X-Authentik or X-Forwarded headers.
OIDC redirect URI is explicitly configured. Future trusted proxy ranges must be
explicit. Caddy/Authenik forward auth may be an outer policy layer but never
substitutes for Portal authentication or internal assertions.

### Secret disclosure

Control: direct/file configuration is mutually exclusive; redacted config output;
no credentials in URLs; no tokens in module status; no raw exception messages;
minimal mounts; separate session and assertion secrets.

## Residual Phase 1A limitations

- real ingress assertion delivery is intentionally not connected;
- live Authentik metadata and logout behavior are not tested;
- password reset email is not implemented; local admin and offline recovery are;
- account disable/delete UI and audit log are later administration work;
- key rotation and asymmetric internal assertions require a later design decision.
