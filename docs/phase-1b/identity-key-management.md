# Internal identity key management

Portal signs Fox Den internal assertions with Ed25519. Only Portal mounts the
PKCS#8 private key. Each module mounts a read-only JWK trust document containing
public keys. Authentik client secrets, OIDC tokens, Portal session cookies, and
Fox Den internal assertions are separate credentials and are never substituted
for one another.

Generate a new pair in a protected administration environment:

```sh
foxden-identity-keygen \
  --private ./secrets/foxden-identity-private.pem \
  --public ./secrets/foxden-identity-public.json \
  --kid foxden-portal-2026-01
```

The generator refuses to overwrite either file and creates the private file as
mode `0600` on POSIX. Keep it on durable local storage, owned by the Portal
container UID, backed up as a secret, and mounted read-only using
`PORTAL_IDENTITY_PRIVATE_KEY_FILE`. Never mount it into ingress or a module.

## Rotation

1. Generate a new pair with a unique `kid`; do not overwrite the active pair.
2. Add the new public JWK to every enabled module trust document while retaining
   the old JWK, then restart and health-check modules.
3. Switch Portal to the new private file and `kid`, then restart and verify both
   local and OIDC-originated sessions through each enabled module.
4. Wait at least two minutes (longer than the maximum 60-second assertion plus
   clock skew and in-flight requests).
5. Remove the old public JWK from module trust documents and restart modules.
6. Retain the old private key only in protected backup until the rollback window
   closes; then destroy it according to the operator's secret-retention policy.

Rollback before step 5 by switching Portal back to the old key. After step 5,
restore the old public JWK to modules before switching Portal back. A missing,
unreadable, overly permissive, symlinked, non-Ed25519, or mismatched private key
causes Portal startup to fail rather than silently disabling authentication.

## Review deployment variables

- Portal: `PORTAL_IDENTITY_PRIVATE_KEY_FILE`,
  `PORTAL_IDENTITY_SIGNING_KID`, `PORTAL_IDENTITY_ISSUER`, and
  `PORTAL_IDENTITY_LIFETIME_SECONDS` (30–60). The private auth subrequest also
  requires `PORTAL_INGRESS_AUTH_SECRET_FILE`; ingress must inject the matching
  value from protected runtime configuration and strip client copies.
- Movies/TV: `FOX_DEN_IDENTITY_PUBLIC_KEYS_FILE` and
  `FOX_DEN_IDENTITY_ISSUER`, plus `FOX_DEN_PUBLIC_ORIGIN` for write protection.
- Music: `FOXDEN_IDENTITY_PUBLIC_KEYS_FILE`, `FOXDEN_IDENTITY_ISSUER`,
  `FOXDEN_IDENTITY_AUDIENCE=music`, `FOXDEN_PUBLIC_ORIGIN`, and
  `WEB_ROOT_PATH=/music` in integrated mode.

The review-only ingress and isolated tests use these settings. Production
Compose and the active production Nginx configuration do not yet consume them.
