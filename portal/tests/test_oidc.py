from dataclasses import replace

from fastapi.testclient import TestClient

from foxden_portal.app import create_app
from foxden_portal.oidc import OIDCError, OIDCUnavailable

from conftest import BOOTSTRAP, bootstrap_admin, settings


class FakeOIDC:
    def __init__(self, outcome="success"):
        self.outcome = outcome

    async def begin(self, return_to="/"):
        if self.outcome == "offline":
            raise OIDCUnavailable("The identity provider is unavailable.")
        return "https://auth.example/authorize?state=safe-state"

    async def finish(self, state, code):
        if self.outcome == "invalid":
            raise OIDCError("ID token validation failed.")
        if self.outcome == "offline":
            raise OIDCUnavailable("The identity provider could not complete login.")
        return ({"sub": "stable-subject", "preferred_username": "foxxin", "name": "Foxxin",
                 "groups": ["foxden-admins"]}, {"return_to": "/"})

    async def discovery(self):
        if self.outcome == "offline":
            raise OIDCUnavailable("The identity provider is unavailable.")
        return {"end_session_endpoint": "https://auth.example/logout"}

    def authorize_claims(self, claims):
        if self.outcome == "unauthorized":
            raise OIDCError("This identity is not authorized for Fox Den Media.")
        return claims["sub"], claims["preferred_username"], claims["name"], claims["groups"], "admin"


def test_successful_oidc_login_creates_local_session(tmp_path):
    configured = settings(tmp_path, auth_mode="hybrid")
    with TestClient(create_app(configured, oidc_client=FakeOIDC())) as client:
        bootstrap_admin(client)
        response = client.get("/auth/oidc/callback?state=state&code=code", follow_redirects=False)
        assert response.status_code == 303
        assert client.get("/").status_code == 200
        assert client.app.state.store.user_by_username("foxxin") is not None


def test_invalid_token_is_rejected(tmp_path):
    configured = settings(tmp_path, auth_mode="hybrid")
    with TestClient(create_app(configured, oidc_client=FakeOIDC("invalid"))) as client:
        bootstrap_admin(client)
        response = client.get("/auth/oidc/callback?state=state&code=code")
        assert response.status_code == 401 and "validation failed" in response.text


def test_oidc_provider_unavailable_does_not_break_local_login(tmp_path):
    configured = settings(tmp_path, auth_mode="hybrid")
    with TestClient(create_app(configured, oidc_client=FakeOIDC("offline"))) as client:
        bootstrap_admin(client)
        assert client.get("/auth/oidc/login").status_code == 503
        assert client.get("/").status_code == 200


def test_unauthorized_group_is_rejected(tmp_path):
    configured = settings(tmp_path, auth_mode="hybrid")
    with TestClient(create_app(configured, oidc_client=FakeOIDC("unauthorized"))) as client:
        bootstrap_admin(client)
        response = client.get("/auth/oidc/callback?state=state&code=code")
        assert response.status_code == 401 and "not authorized" in response.text


def test_oidc_disabled_returns_not_found(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        assert client.get("/auth/oidc/login").status_code == 404


def test_provider_logout_revokes_local_session_and_redirects_safely(tmp_path):
    configured = replace(settings(tmp_path, auth_mode="hybrid"), oidc_logout="provider")
    with TestClient(create_app(configured, oidc_client=FakeOIDC())) as client:
        bootstrap_admin(client)
        client.get("/auth/oidc/callback?state=state&code=code", follow_redirects=False)
        csrf = client.cookies.get("foxden_portal_csrf")
        response = client.post("/logout", data={"csrf": csrf}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("https://auth.example/logout?")
        assert client.get("/", follow_redirects=False).headers["location"] == "/login"


def test_provider_outage_cannot_prevent_local_logout(tmp_path):
    configured = replace(settings(tmp_path, auth_mode="hybrid"), oidc_logout="provider")
    with TestClient(create_app(configured, oidc_client=FakeOIDC("offline"))) as client:
        bootstrap_admin(client)
        # Create an OIDC-sourced Portal session without depending on a live provider.
        user = client.app.state.store.map_external_identity(
            configured.oidc_issuer, "subject", "foxxin", "Foxxin", {"sub": "subject"}, "user")
        token, csrf = client.app.state.store.create_session(user["id"], "oidc", configured.session_seconds)
        client.cookies.set("foxden_portal_session", token)
        client.cookies.set("foxden_portal_csrf", csrf)
        response = client.post("/logout", data={"csrf": csrf}, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/login"
        assert client.app.state.store.session(token) is None
