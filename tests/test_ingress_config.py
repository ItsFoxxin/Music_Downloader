from pathlib import Path


CONFIG = (Path(__file__).parents[1] / "gateway" / "portal-ingress.conf").read_text(encoding="utf-8")


def test_portal_is_root_and_auth_authority():
    assert "set $portal_backend portal:8020;" in CONFIG
    assert "proxy_pass http://$portal_backend/api/platform/v1/session;" in CONFIG
    assert "location / {" in CONFIG
    assert "set $auth_backend media:8010" not in CONFIG
    assert "audience=music" in CONFIG and "audience=media" in CONFIG
    assert "auth_request_set $foxden_music_identity" in CONFIG
    assert "auth_request_set $foxden_media_identity" in CONFIG


def test_optional_modules_use_deferred_resolution_and_safe_failure():
    for backend in ("music:8000", "media:8010", "download-browser:5800"):
        assert f"set $" in CONFIG and backend in CONFIG
    assert "resolver 127.0.0.11" in CONFIG
    assert CONFIG.count("error_page 502 503 504 = @module_unavailable;") == 3
    assert 'return 503 "Module unavailable\\n";' in CONFIG


def test_ingress_strips_identity_headers_and_preserves_transport_controls():
    assert CONFIG.count('proxy_set_header X-FoxDen-Identity "";') == 5
    for header in ("X-Authentik-Username", "X-Authentik-Groups", "X-Authentik-Email",
                   "X-Authentik-Uid", "X-Authentik-Jwt"):
        assert CONFIG.count(f'proxy_set_header {header} "";') == 7
    assert CONFIG.count('proxy_set_header X-FoxDen-Ingress "";') == 4
    assert CONFIG.count('proxy_set_header X-FoxDen-Ingress "1";') == 3
    assert "proxy_set_header X-FoxDen-Identity $foxden_music_identity;" in CONFIG
    assert "proxy_set_header X-FoxDen-Identity $foxden_media_identity;" in CONFIG
    assert CONFIG.count("error_page 500 = @auth_unavailable;") == 2
    assert "proxy_request_buffering off;" in CONFIG
    assert "proxy_set_header Upgrade $http_upgrade;" in CONFIG
    assert "proxy_set_header Connection $connection_upgrade;" in CONFIG
    assert CONFIG.count("proxy_set_header X-Forwarded-Proto $scheme;") == 4
    assert CONFIG.count("proxy_set_header X-Forwarded-Host $http_host;") == 4
