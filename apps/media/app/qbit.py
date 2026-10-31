from pathlib import PurePosixPath
import httpx
import threading
import time


class Qbit:
    def __init__(self, settings):
        self.s = settings
        self.lock = threading.RLock()
        self.session = None
        self.auth_retry_after = 0

    def call(self, path, data=None):
        if not self.s.qbit_url:
            raise ValueError("qBittorrent is not configured. Set QBIT_URL and credentials.")
        with self.lock:
            try:
                if self.session is None:
                    self.session = httpx.Client(base_url=self.s.qbit_url + "/", timeout=20, follow_redirects=False,
                                                headers={"Referer": self.s.qbit_url + "/"})
                client = self.session
                for attempt in range(2):
                    if not client.cookies:
                        if time.monotonic() < self.auth_retry_after:
                            raise ValueError("qBittorrent login failed recently. Check credentials; retry is limited to once per minute.")
                        self.auth_retry_after = time.monotonic() + 60
                        auth = client.post("api/v2/auth/login", data={"username": self.s.qbit_user, "password": self.s.qbit_password})
                        if auth.status_code != 200 or auth.text.strip() != "Ok.":
                            raise ValueError("qBittorrent login failed. Check credentials and Web UI access settings.")
                        self.auth_retry_after = 0
                    response = client.get("api/v2/" + path) if data is None else client.post("api/v2/" + path, data=data)
                    if response.status_code == 403 and attempt == 0:
                        client.cookies.clear()
                        continue
                    response.raise_for_status()
                    return response.json() if "json" in response.headers.get("content-type", "") else response.text
            except httpx.HTTPError:
                raise ValueError("qBittorrent could not be reached or rejected the request. Check its URL and connection.") from None

    def torrents(self):
        return self.call("torrents/info")

    def files(self, torrent_hash):
        return self.call("torrents/files?hash=" + torrent_hash)

    def action(self, torrent_hash, action):
        if action not in {"start", "stop", "recheck"}:
            raise ValueError("Unsupported torrent action")
        version = str(self.call("app/version")).lstrip("v")
        endpoint = {"start": "resume", "stop": "pause"}.get(action, action) if version.startswith("4.") else action
        self.call("torrents/" + endpoint, {"hashes": torrent_hash})

    def add(self, magnet, category):
        if not magnet.startswith("magnet:?") or "xt=urn:bt" not in magnet or len(magnet) > 8192:
            raise ValueError("Provide a valid magnet link.")
        response = self.call("torrents/add", {"urls": magnet, "category": category})
        if str(response).strip() != "Ok.":
            raise ValueError("qBittorrent did not accept the magnet link.")

    def manifest(self, torrent_hash):
        torrents = [t for t in self.torrents() if t["hash"] == torrent_hash]
        if not torrents:
            raise ValueError("Torrent is no longer available.")
        torrent = torrents[0]
        if torrent.get("progress", 0) < 1 or torrent.get("amount_left", 1) != 0:
            raise ValueError("Torrent has not completed downloading.")
        if torrent.get("state", "").lower() not in {"uploading", "stalledup", "pausedup", "stoppedup", "queuedup", "forcedup"}:
            raise ValueError("Torrent is checking, moving, or not in a completed state. Try again after it settles.")
        root = PurePosixPath(self.s.qbit_download_root.replace("\\", "/"))
        save = PurePosixPath(torrent["save_path"].replace("\\", "/"))
        try:
            relative = save.relative_to(root)
        except ValueError:
            raise ValueError("Torrent save path is outside QBIT_DOWNLOAD_ROOT; check the container path mapping.") from None
        files = self.files(torrent_hash)
        selected = [f for f in files if f.get("priority", 1) != 0]
        if not selected or any(f.get("progress", 0) < 1 for f in selected):
            raise ValueError("Selected torrent files are incomplete.")
        return [{"path": (relative / f["name"]).as_posix(), "size": f["size"]} for f in selected]
