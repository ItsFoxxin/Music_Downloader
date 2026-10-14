"""Release UI checks using a temporary DB; no NAS, provider, or API credentials."""
import io
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:18040"


def serve(folder):
    import uvicorn
    from foxden_music.config import Settings
    from foxden_music.web import create_app
    settings = Settings(_env_file=None, app_environment="test",
        config_dir=folder / "config", staging_dir=folder / "staging",
        music_dir=folder / "music", database_url=f"sqlite:///{folder.as_posix()}/test.db",
        download_inbox_dir=folder / "downloads", remote_browser_url="/server-browser/",
        csrf_secret="ci-only-not-a-production-secret-123456789",
        musicbrainz_contact=None, jellyfin_url=None, jellyfin_api_key=None)
    settings.download_inbox_dir.mkdir()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=18040)


def check():
    import httpx
    from playwright.sync_api import sync_playwright
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="foxden-ci-ui-") as temporary:
        with (reports / "browser-server.log").open("w") as log:
            server = subprocess.Popen([sys.executable, __file__, "--serve", temporary], stdout=log, stderr=log)
            try:
                for _ in range(60):
                    if server.poll() is not None:
                        raise RuntimeError("Preview server exited; inspect browser-server.log")
                    try:
                        if httpx.get(BASE + "/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.5)
                else:
                    raise RuntimeError("Preview startup timeout")
                with sync_playwright() as playwright:
                    for engine in ("chromium", "webkit"):
                        browser = getattr(playwright, engine).launch()
                        try:
                            for width in (1440, 390):
                                context = browser.new_context(viewport={"width": width, "height": 900},
                                    is_mobile=width < 500, has_touch=width < 500)
                                page = context.new_page()
                                errors = []
                                page.on("pageerror", lambda error: errors.append(str(error)))
                                page.route("**/server-browser/**", lambda route: route.fulfill(
                                    content_type="text/html", body="<html><body>CI viewer placeholder</body></html>"))
                                for route in ("/", "/add", "/acquisitions", "/review", "/history",
                                    "/library", "/library/albums", "/library/artists", "/library/health"):
                                    response = page.goto(BASE + route)
                                    assert response.status == 200, route
                                    assert page.locator("h1").count() == 1, route
                                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), route
                                    assert page.get_by_role("navigation", name="Main navigation", exact=True).is_visible()
                                page.goto(BASE)
                                page.screenshot(path=str(reports / f"{engine}-{width}.png"), full_page=True)
                                page.get_by_role("navigation", name="Main navigation", exact=True).get_by_role("link", name="Add music", exact=True).click()
                                page.get_by_label("Spotify URLs").fill("https://open.spotify.com/track/1234567890123456789012")
                                page.get_by_role("button", name="Add all to queue", exact=True).click()
                                page.wait_for_url("**/acquisitions?created=1")
                                page.locator("tbody a").first.click()
                                acquisition_url = page.url
                                # Start the watched session through its CSRF-protected endpoint.
                                # Clipboard permissions differ between browser engines.
                                form = page.locator("form[data-copy-open-form]")
                                token = form.locator('input[name="csrf_token"]').input_value()
                                response = context.request.post(BASE + form.get_attribute("action"), form={"csrf_token": token})
                                assert response.status == 200
                                page.goto(acquisition_url + "/browser")
                                assert page.get_by_role("button", name="Downloader home", exact=True).is_visible()
                                assert page.locator(".sidebar").count() == 0
                                page.get_by_role("link", name="Back to request", exact=True).click()
                                assert "WAITING FOR DOWNLOAD" in page.locator("body").inner_text()
                                page.get_by_role("button", name="Cancel request", exact=True).click()
                                page.wait_for_load_state()
                                assert "CANCELLED" in page.locator("body").inner_text()
                                # Real multipart intake; downstream audio processing is tested separately.
                                page.goto(BASE + "/add")
                                payload = io.BytesIO()
                                with zipfile.ZipFile(payload, "w") as archive:
                                    archive.writestr("fixture.flac", b"fLaC-ci-intake-fixture")
                                page.locator("[data-upload-file]").set_input_files({
                                    "name": "ci-album.zip", "mimeType": "application/zip", "buffer": payload.getvalue()})
                                page.get_by_role("button", name="Queue direct import", exact=True).click()
                                page.wait_for_url(re.compile(r".*/jobs/[^/]+$"))
                                assert "QUEUED" in page.locator("body").inner_text()
                                assert not errors, errors
                                context.close()
                                print(f"{engine} {width}px: navigation, queue/start/cancel, browser return and upload passed")
                        finally:
                            browser.close()
            finally:
                server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve(Path(sys.argv[2]))
    else:
        check()
