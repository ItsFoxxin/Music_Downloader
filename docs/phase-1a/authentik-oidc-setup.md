# Authentik OIDC and Caddy integration plan

Status: exact pre-live configuration; do not apply during Phase 1A

Replace media.example.com and auth.example.com with the operator’s real HTTPS
names. Do not use wildcard redirect URIs.

## Authentik application and provider

In Authentik Admin:

1. Open Applications, create a new application and provider.
2. Application name: Fox Den Media.
3. Suggested slug: fox-den-media.
4. Provider type: OAuth2/OpenID Connect.
5. Client type: Confidential.
6. Grant: Authorization Code. Do not enable implicit flow for Portal.
7. Redirect URI, strict match:

       https://media.example.com/auth/oidc/callback

8. Select a signing key and retain the generated client ID/secret securely.
9. Scope mappings: openid, profile, email. The Authentik profile scope supplies
   basic profile and group membership. No Authentik API scope is required.
10. Bind an Authentik policy/group that is allowed to access the application.

Discovery URL for slug fox-den-media:

    https://auth.example.com/application/o/fox-den-media/.well-known/openid-configuration

Portal issuer configuration is the issuer value returned by that document,
normally:

    https://auth.example.com/application/o/fox-den-media

## Portal configuration

    PORTAL_AUTH_MODE=hybrid
    PORTAL_PUBLIC_URL=https://media.example.com
    PORTAL_COOKIE_SECURE=true
    PORTAL_OIDC_ISSUER=https://auth.example.com/application/o/fox-den-media
    PORTAL_OIDC_CLIENT_ID=<generated-client-id>
    PORTAL_OIDC_CLIENT_SECRET_FILE=/run/secrets/portal_oidc_client_secret
    PORTAL_OIDC_REDIRECT_URI=https://media.example.com/auth/oidc/callback
    PORTAL_OIDC_SCOPES=openid profile email
    PORTAL_OIDC_ALLOWED_GROUPS=Fox Den Users,Fox Den Administrators
    PORTAL_OIDC_ADMIN_GROUPS=Fox Den Administrators
    PORTAL_OIDC_LOGOUT=provider

Hybrid mode keeps local emergency administration. OIDC-only mode requires an
administrator-group mapping. Local remains the default for new installations.

## Caddy

Native Portal OIDC is preferred. Caddy terminates TLS and proxies the Portal
ingress; do not put Authentik forward_auth in front of Portal login routes, because
that would make Authentik a prerequisite and block local emergency login.

Conceptual Caddy site:

    media.example.com {
        encode zstd gzip
        reverse_proxy foxden-ingress:8080 {
            header_up X-Forwarded-Proto https
            header_up -X-FoxDen-Identity
            header_up -X-Authentik-Username
            header_up -X-Authentik-Groups
            header_up -X-Authentik-Email
            header_up -X-Authentik-Uid
            header_up -X-Authentik-Jwt
        }
    }

The final trusted-proxy ranges and ingress header rules are a later gateway task.
Portal never treats X-Authentik headers as authentication.

If an outer Authentik forward-auth policy is retained for defense in depth, Portal
authentication still runs, local recovery paths must be deliberately reachable,
and client identity headers must be stripped before trusted platform assertions
are added. Verify the installed Authentik release against current security
advisories before enabling forward auth.

## Outage behavior

- OIDC login initiation/callback returns a safe unavailable page.
- Portal health and login page remain available.
- Hybrid local login remains available.
- Existing Portal sessions remain valid until expiration/revocation.
- OIDC-only users without an existing session cannot create a bypass; they wait
  for Authentik recovery.
- A restricted local emergency administrator is created explicitly and protected
  like any other local account; it is never a default credential.
- Module health and authentication are not derived from Authentik availability.

## Live acceptance before enabling

- verify exact issuer and JWKS from discovery;
- verify strict redirect and HTTPS headers;
- test allowed and denied groups;
- test administrator mapping;
- test state, nonce, PKCE, invalid signature, wrong audience, and expiration;
- test local, provider, and combined logout expectations;
- test Authentik outage with an existing Portal session and local emergency login;
- verify Caddy strips identity headers supplied by a client;
- record Authentik, Caddy, Portal, and ingress versions.
