import re
import sqlite3
import time

from fastapi.testclient import TestClient

from foxden_portal.app import create_app

from conftest import BOOTSTRAP, PASSWORD, bootstrap_admin, csrf, login, settings


def test_fresh_install_requires_bootstrap_and_creates_admin(local_client):
    assert local_client.get("/", follow_redirects=False).headers["location"] == "/setup"
    bootstrap_admin(local_client)
    page = local_client.get("/")
    assert page.status_code == 200 and "Fox Admin" in page.text


def test_wrong_bootstrap_cannot_claim_admin(local_client):
    page = local_client.get("/setup")
    response = local_client.post("/setup", data={"csrf": csrf(page.text), "bootstrap_secret": "wrong",
        "username": "attacker", "display_name": "Attacker", "password": PASSWORD})
    assert response.status_code == 400
    assert local_client.app.state.store.has_admin() is False


def test_bootstrap_is_one_time(local_client):
    bootstrap_admin(local_client)
    other = TestClient(local_client.app)
    assert other.get("/setup", follow_redirects=False).headers["location"] == "/login"


def test_expired_bootstrap_is_rejected(tmp_path):
    configured = settings(tmp_path)
    with TestClient(create_app(configured)) as client:
        with client.app.state.store.connection() as db:
            db.execute("UPDATE portal_metadata SET value=? WHERE key='first_started_at'", (str(int(time.time()) - 4000),))
        page = client.get("/setup")
        response = client.post("/setup", data={"csrf": csrf(page.text), "bootstrap_secret": BOOTSTRAP,
            "username": "admin", "display_name": "Admin", "password": PASSWORD})
        assert response.status_code == 400 and "expired" in response.text


def test_login_logout_and_unauthorized_access(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        token = client.cookies.get("foxden_portal_csrf")
        assert client.post("/logout", data={"csrf": token}, follow_redirects=False).status_code == 303
        assert client.get("/api/platform/v1/status").status_code == 401
        assert login(client).status_code == 303


def test_incorrect_password_is_generic_and_rate_limited(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        client.post("/logout", data={"csrf": client.cookies.get("foxden_portal_csrf")})
        for _ in range(3):
            response = login(client, password="Definitely-Wrong-4!")
            assert "Username or password is incorrect" in response.text
        locked = login(client)
        assert locked.status_code == 429 and "Too many login attempts" in locked.text
        assert "Correct-Horse" not in locked.text


def test_expired_session_is_rejected(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        with client.app.state.store.connection() as db:
            db.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
        assert client.get("/", follow_redirects=False).headers["location"] == "/login"


def test_accounts_persist_across_restart(tmp_path):
    configured = settings(tmp_path)
    with TestClient(create_app(configured)) as client:
        bootstrap_admin(client)
    with TestClient(create_app(configured)) as restarted:
        assert restarted.get("/setup", follow_redirects=False).headers["location"] == "/login"
        assert login(restarted).status_code == 303


def test_admin_can_create_and_reset_local_account(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        bootstrap_admin(client)
        page = client.get("/admin/users")
        token = csrf(page.text)
        created = client.post("/admin/users", data={"csrf": token, "username": "listener",
            "display_name": "Listener", "password": "Listener-Password-8!", "role": "user"})
        assert created.status_code == 200 and "@listener" in created.text
        reset = client.post("/admin/users/reset-password", data={"csrf": token, "username": "listener",
            "password": "Changed-Password-9!"})
        assert reset.status_code == 200
        client.post("/logout", data={"csrf": token})
        assert login(client, "listener", "Changed-Password-9!").status_code == 303


def test_csrf_is_required(local_client):
    bootstrap_admin(local_client)
    assert local_client.post("/logout", data={"csrf": "forged"}).status_code == 403


def test_ingress_session_check_exposes_no_identity_or_secret(local_client):
    anonymous = local_client.get("/api/platform/v1/session")
    assert anonymous.status_code == 401 and anonymous.content == b""
    bootstrap_admin(local_client)
    authenticated = local_client.get("/api/platform/v1/session")
    assert authenticated.status_code == 204 and authenticated.content == b""
    assert "x-foxden-identity" not in authenticated.headers
