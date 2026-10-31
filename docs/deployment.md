# Modular deployment

Fox Den uses one Compose model with profiles selected by `scripts/foxden.py`.
Users configure host-specific values only through an environment file and
secret files.

| Mode | Profiles | Services |
|---|---|---|
| `music` | `music` | ingress, Portal, Music web, Music worker |
| `media` | `media` | ingress, Portal, Movies/TV |
| `full-external` | `music`, `media` | both modules with external qBittorrent and optional external Jellyfin |
| `full-managed` | `music`, `media`, `managed` | both modules, qBittorrent, and Gluetun |

`--browser` adds the optional contained browser. Disabled profiles do not make
their configuration mandatory.

## Initial configuration

1. Copy the matching file from `deploy/examples` to an untracked `.env`.
2. Replace example paths, public origin, IDs, and provider values.
3. Run `python scripts/foxden.py init --env .env --create-paths`.
4. Put the real qBittorrent password and, for managed mode, WireGuard private
   key into the generated secret files. If Jellyfin or OIDC is enabled, fill
   `jellyfin-api-key` or `oidc-client-secret` respectively. The command never
   prints them.
5. Run `python scripts/foxden.py validate MODE --env .env`.
6. Review `python scripts/foxden.py deploy MODE --env .env`.
7. Only after approval, repeat with `--execute`.

The gateway configuration is rendered from a tracked template into the runtime
directory with the ingress authentication secret. It is never committed.

## Reverse proxies and Authentik

Bind ingress to loopback when Caddy terminates TLS. Set `FOXDEN_PUBLIC_ORIGIN`
to the external HTTPS origin and keep `PORTAL_COOKIE_SECURE=true`. Authentik is
optional; set Portal to `oidc` or `hybrid` and configure issuer, client ID,
client-secret file, redirect URI, and group mappings. Caddy or forward-auth
headers are not accepted as module identity; Portal mints separate Ed25519
assertions after authentication.

## Jellyfin boundary

The first migration keeps Jellyfin external. Set `JELLYFIN_URL` and place the
API key in the generated `jellyfin-api-key` secret; only the Music worker sees
that file. Leave the URL blank when refresh is not wanted. Existing libraries
are bind-mounted at stable paths so a future managed Jellyfin phase will not
require moving media.
