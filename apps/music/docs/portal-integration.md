# Fox Den Portal integration (0.4.1 review branch)

This branch is based on recorded authoritative `Music_Downloader/dev` commit
`b4bbffbb2a739a8b78ec6b194416b8d4fb5e09ea`. It is intentionally independent
of the current Music release PR and is not a production deployment.

Standalone Music remains the default. Portal integration activates only when
`FOXDEN_IDENTITY_PUBLIC_KEYS_FILE` points to a readable JWK trust document and
`FOXDEN_PUBLIC_ORIGIN` contains the exact browser origin. In that mode:

- public health and contract summary endpoints remain available;
- every Music UI and API request requires a short-lived Portal Ed25519
  assertion with issuer `foxden-portal`, audience `music`, token use `user`,
  scope `module:access`, and role `user` or `admin`;
- GET/HEAD access is available to restricted users;
- writes require the `admin` role, the exact configured `Origin`, and Music's
  existing signed form-CSRF token;
- `GET /api/platform/v1/activity` accepts only a separate service assertion
  with scope `activity:read` and returns aggregate, presentation-safe status;
- `X-FoxDen-Ingress` is ignored and cannot authenticate a caller;
- `/music/` asset, form, polling, API, and redirect paths are generated when
  `WEB_ROOT_PATH=/music`.

Music receives only the public trust set. Portal retains the private Ed25519
key. During rotation, deploy a trust set containing old and new public JWKs,
switch Portal's signing key ID, wait longer than the maximum 60-second token
lifetime plus skew, and then remove the old public JWK.

The replay cache is deliberately process-local and bounded. A safe restart
accepts newly issued Portal assertions using the persistent public trust file.
Because assertions are never exposed to the browser and expire within 60
seconds, restart does not introduce a durable bearer-token store.
