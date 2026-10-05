from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
import os


@dataclass
class Settings:
    config: Path = field(default_factory=lambda: Path(os.getenv("CONFIG_DIR", "data/config")).absolute())
    staging: Path = field(default_factory=lambda: Path(os.getenv("STAGING_DIR", "data/staging")).absolute())
    media: Path = field(default_factory=lambda: Path(os.getenv("MEDIA_DIR", "data/media")).absolute())
    qbit_url: str = field(default_factory=lambda: os.getenv("QBIT_URL", "").rstrip("/"))
    qbit_public_url: str = field(default_factory=lambda: os.getenv("QBIT_PUBLIC_URL", ""))
    qbit_user: str = field(default_factory=lambda: os.getenv("QBIT_USERNAME", "admin"))
    qbit_password: str = field(default_factory=lambda: os.getenv("QBIT_PASSWORD", ""))
    qbit_download_root: str = field(default_factory=lambda: os.getenv("QBIT_DOWNLOAD_ROOT", "/downloads"))
    token: str = field(default_factory=lambda: os.getenv("APP_TOKEN", ""))
    ffprobe: str = field(default_factory=lambda: os.getenv("FFPROBE_PATH", "ffprobe"))
    ffmpeg: str = field(default_factory=lambda: os.getenv("FFMPEG_PATH", "ffmpeg"))
    full_decode: bool = field(default_factory=lambda: os.getenv("FULL_DECODE", "true").lower() == "true")
    settle_seconds: float = field(default_factory=lambda: float(os.getenv("SETTLE_SECONDS", "3")))
    decode_timeout: int = field(default_factory=lambda: int(os.getenv("DECODE_TIMEOUT", "14400")))
    max_files: int = 10000
    demo: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "false").lower() == "true")
    cookie_secure: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true")

    def prepare(self):
        if len(self.token) < 24:
            raise ValueError("Set APP_TOKEN to a random value of at least 24 characters.")
        for url in (self.qbit_url, self.qbit_public_url):
            if url:
                parsed = urlsplit(url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError("qBittorrent URLs must be HTTP(S), without embedded credentials.")
        for root in (self.config, self.staging, self.media):
            root.mkdir(parents=True, exist_ok=True)
        roots = [p.resolve() for p in (self.config, self.staging, self.media)]
        for i, a in enumerate(roots):
            for b in roots[i + 1:]:
                if a == b or a in b.parents or b in a.parents:
                    raise ValueError("Config, staging, and media must be separate, non-overlapping directories.")
        self.config, self.staging, self.media = roots
