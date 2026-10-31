from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from .config import Settings
from .enums import AcquisitionProvider
from .models import AcquisitionJob


class ProviderAdapterError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderHandoff:
    provider: AcquisitionProvider
    requires_user: bool
    public_url: str | None
    download_directory: Path
    action: str


class AcquisitionAdapter(Protocol):
    provider: AcquisitionProvider

    def prepare(self, request: AcquisitionJob, settings: Settings) -> ProviderHandoff: ...


def request_download_directory(request: AcquisitionJob, settings: Settings) -> Path:
    if settings.download_inbox_dir is None:
        raise ProviderAdapterError("DOWNLOAD_INBOX_DIR is required for acquisition providers")
    root = settings.download_inbox_dir.resolve(strict=True)
    destination = (root / request.id).resolve(strict=False)
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ProviderAdapterError("Request download directory escaped the configured inbox") from exc
    destination.mkdir(mode=0o750, parents=True, exist_ok=True)
    return destination


class ManualBrowserAdapter:
    provider = AcquisitionProvider.MANUAL_BROWSER

    def prepare(self, request: AcquisitionJob, settings: Settings) -> ProviderHandoff:
        value = settings.music_request_provider_url
        if not value:
            raise ProviderAdapterError("MUSIC_REQUEST_PROVIDER_URL is required for MANUAL_BROWSER")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderAdapterError("MUSIC_REQUEST_PROVIDER_URL must be a public HTTPS URL without credentials")
        return ProviderHandoff(
            provider=self.provider,
            requires_user=True,
            public_url=value,
            download_directory=request_download_directory(request, settings),
            action="Complete any login, CAPTCHA, or ambiguous provider choice in the contained browser",
        )


class FilesystemDropAdapter:
    provider = AcquisitionProvider.FILESYSTEM_DROP

    def prepare(self, request: AcquisitionJob, settings: Settings) -> ProviderHandoff:
        return ProviderHandoff(
            provider=self.provider,
            requires_user=False,
            public_url=None,
            download_directory=request_download_directory(request, settings),
            action="Place the completed provider output in this request directory",
        )


def provider_adapter(value: AcquisitionProvider | str) -> AcquisitionAdapter:
    provider = AcquisitionProvider(value)
    if provider is AcquisitionProvider.MANUAL_BROWSER:
        return ManualBrowserAdapter()
    if provider is AcquisitionProvider.FILESYSTEM_DROP:
        return FilesystemDropAdapter()
    raise ProviderAdapterError("The legacy provider is supported only by legacy acquisition jobs")
