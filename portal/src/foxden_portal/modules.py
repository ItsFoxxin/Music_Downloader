from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

import httpx
from pydantic import ValidationError

from .config import ModuleConfig
from .contracts import ActivityFeed, IDENTITY_HEADER, ModuleSummary


@dataclass(frozen=True)
class ModuleSnapshot:
    module_id: str
    name: str
    navigation_path: str
    state: str
    summary: str
    version: str | None = None
    capabilities: tuple[dict, ...] = ()
    activity: tuple[dict, ...] = ()


class ModuleClient:
    def __init__(self, timeout_seconds: float, transport: httpx.AsyncBaseTransport | None = None,
                 service_assertion=None):
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.service_assertion = service_assertion

    async def fetch(self, module: ModuleConfig) -> ModuleSnapshot:
        try:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport, follow_redirects=False) as client:
                response = await client.get(module.base_url + "/api/platform/v1/summary",
                                            headers={"Accept": "application/json"})
                if response.status_code != 200:
                    return self._offline(module, "Module returned an unavailable response.")
                if len(response.content) > 128 * 1024:
                    return self._invalid(module)
                summary = ModuleSummary.model_validate(response.json())
                # Public health reachability never authorizes activity disclosure.
                activity = ()
                if self.service_assertion:
                    try:
                        activity_response = await client.get(
                            module.base_url + "/api/platform/v1/activity",
                            headers={"Accept": "application/json",
                                     IDENTITY_HEADER: self.service_assertion(module.module_id)},
                        )
                        if activity_response.status_code == 200 and len(activity_response.content) <= 128 * 1024:
                            feed = ActivityFeed.model_validate(activity_response.json())
                            if feed.module_id == module.module_id:
                                activity = tuple(item.model_dump() for item in feed.activity[:10])
                    except (httpx.HTTPError, asyncio.TimeoutError, ValueError, ValidationError):
                        # Health remains useful even when private activity is unavailable or invalid.
                        activity = ()
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return self._offline(module, "Module timed out.")
        except httpx.HTTPError:
            return self._offline(module, "Module is offline.")
        except (ValueError, ValidationError):
            return self._invalid(module)
        if summary.module_id != module.module_id:
            return self._invalid(module)
        state = "healthy" if summary.health.status == "healthy" else "unhealthy"
        capabilities = tuple(item.model_dump() for item in summary.capabilities)
        return ModuleSnapshot(module.module_id, module.name, module.navigation_path, state,
                              summary.health.summary, summary.module_version, capabilities, activity)

    @staticmethod
    def _offline(module: ModuleConfig, message: str) -> ModuleSnapshot:
        return ModuleSnapshot(module.module_id, module.name, module.navigation_path, "offline", message)

    @staticmethod
    def _invalid(module: ModuleConfig) -> ModuleSnapshot:
        return ModuleSnapshot(module.module_id, module.name, module.navigation_path, "unhealthy",
                              "Module returned an invalid platform response.")


class ModuleRegistry:
    def __init__(self, modules: tuple[ModuleConfig, ...], client: ModuleClient):
        self.modules = modules
        self.client = client

    async def snapshots(self) -> list[ModuleSnapshot]:
        enabled = [module for module in self.modules if module.enabled]
        if not enabled:
            return []
        results = await asyncio.gather(*(self.client.fetch(module) for module in enabled), return_exceptions=True)
        snapshots: list[ModuleSnapshot] = []
        for module, result in zip(enabled, results, strict=True):
            if isinstance(result, BaseException):
                snapshots.append(ModuleSnapshot(module.module_id, module.name, module.navigation_path,
                                                "offline", "Module is offline."))
            else:
                snapshots.append(result)
        return snapshots

    @staticmethod
    def combined_activity(snapshots: list[ModuleSnapshot]) -> list[dict]:
        combined: list[dict] = []
        for snapshot in snapshots:
            for item in snapshot.activity:
                combined.append({**item, "module_id": snapshot.module_id, "module_name": snapshot.name})
        return sorted(combined, key=lambda item: item["occurred_at"], reverse=True)[:20]
