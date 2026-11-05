"""One local connection; refresh parameters by group in the executor."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MangoClient, MangoWriteError
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .executor import async_call
from .protocol import Field, MangoError, MangoValueError, Parameter, Profile, Snapshot

LOGGER = logging.getLogger(__name__)


class MangoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, profile: Profile, client: MangoClient):
        self.profile, self.client, self.entry = profile, client, entry
        self.descriptions: dict[str, dict[str, str]] = {}
        self.interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=self.interval),
            always_update=False,
        )
        self.snapshots: dict[int, Snapshot] = {}
        self.failed_groups: set[int] = set()
        self._io_lock = asyncio.Lock()
        self._next_group = 0
        self._retry_group: int | None = None
        self._last_contact_monotonic: float | None = None
        self.connection_state = "connecting"
        self.consecutive_status_failures = 0
        self._scan_task: asyncio.Task | None = None
        self._closing = False

    def current_data(self) -> dict[str, Any]:
        return {
            "groups": dict(self.snapshots),
            "failed_groups": frozenset(self.failed_groups),
            "temperatures": dict(self.client.temperatures),
            "temperature_received_at": self.client.temperature_received_at,
            "connection_state": self.connection_state,
            "consecutive_status_failures": self.consecutive_status_failures,
        }

    @property
    def connection_grace_seconds(self) -> int:
        return min(120, self.interval * 3 + 10)

    def _mark_contact(self) -> None:
        self._last_contact_monotonic = time.monotonic()
        self.connection_state = "connected"
        self.consecutive_status_failures = 0

    async def _executor(self, method, *args, abort: threading.Event | None = None):
        return await async_call(self.hass, method, *args, abort=abort)

    async def _async_update_data(self) -> dict[str, Any]:
        if self._closing:
            raise UpdateFailed("Local client is closing")
        async with self._io_lock:
            try:
                await self._executor(self.client.status)
            except MangoError as error:
                self.consecutive_status_failures += 1
                self.connection_state = "retrying"
                if (
                    self.snapshots
                    and self._last_contact_monotonic is not None
                    and time.monotonic() - self._last_contact_monotonic <= self.connection_grace_seconds
                ):
                    LOGGER.debug("Mango status retry pending (%s)", self.client.last_transport_error)
                    return self.current_data()
                self.connection_state = "offline"
                raise UpdateFailed(
                    f"Local device connection failed ({self.client.last_transport_error or 'read_failed'})"
                ) from error
            self._mark_contact()
            # During initial full scan, the background worker supplies metadata.
            if self._scan_task is None or self._scan_task.done():
                retry = self._retry_group is not None
                if retry:
                    group, self._retry_group = self._retry_group, None
                else:
                    group = self._next_group
                    self._next_group = (group + 1) % 17
                try:
                    self.snapshots[group] = await self._executor(self.client.read_group, group)
                    self.failed_groups.discard(group)
                except MangoError as error:
                    self.failed_groups.add(group)
                    if not retry:
                        self._retry_group = group
                    if not self.snapshots:
                        raise UpdateFailed("Matching Mango parameter descriptions unavailable") from error
            return self.current_data()

    def field(self, parameter: Parameter) -> Field | None:
        snapshot = self.snapshots.get(parameter.group)
        return snapshot.field(parameter) if snapshot is not None else None

    def parameter_available(self, parameter: Parameter) -> bool:
        if (
            not self.last_update_success
            or self.connection_state == "offline"
            or parameter.group in self.failed_groups
        ):
            return False
        snapshot = self.snapshots.get(parameter.group)
        if snapshot is None or time.time() - snapshot.received_at > self.interval * 34 + 60:
            return False
        field = snapshot.field(parameter)
        if (parameter.scale_verified or parameter.key in self.profile.known_select_options) and (
            field.flags != parameter.flags or field.tag != parameter.tag
        ):
            return False
        return True

    async def async_set_raw(self, parameter: Parameter, value: int) -> None:
        if self._closing:
            raise HomeAssistantError("Local device is closing")
        abort = threading.Event()
        async with self._io_lock:
            try:
                result = await self._executor(self.client.set_raw, parameter, value, abort, abort=abort)
            except asyncio.CancelledError:
                # A cancelled caller has no returned snapshot, even if recovery
                # finished. Do not show an old cached value as confirmed current.
                self.failed_groups.add(parameter.group)
                self._retry_group = parameter.group
                self.async_set_updated_data(self.current_data())
                raise
            except MangoValueError as error:
                raise ServiceValidationError("Value is not within the device's fresh raw bounds") from error
            except MangoWriteError as error:
                if error.snapshot is not None:
                    self.snapshots[parameter.group] = error.snapshot
                    self.failed_groups.discard(parameter.group)
                    self._mark_contact()
                else:
                    self.failed_groups.add(parameter.group)
                    self._retry_group = parameter.group
                self.async_set_updated_data(self.current_data())
                if error.restored:
                    raise HomeAssistantError(
                        "Device did not confirm the requested value. Original value was restored."
                    ) from error
                raise HomeAssistantError(
                    f"Write and restore could not be confirmed. Restore {parameter.name} to raw {error.original} in the device app."
                ) from error
            except MangoError as error:
                self.failed_groups.add(parameter.group)
                self._retry_group = parameter.group
                self.async_set_updated_data(self.current_data())
                raise HomeAssistantError(
                    "Matching parameter reply unavailable; no confirmed change"
                ) from error
            self.snapshots[parameter.group] = result.snapshot
            self.failed_groups.discard(parameter.group)
            self._mark_contact()
            self.async_set_updated_data(self.current_data())

    def async_start_scan(self) -> None:
        if self._closing or self._scan_task is not None and not self._scan_task.done():
            return
        self._scan_task = self.entry.async_create_background_task(
            self.hass, self._async_scan_all(), "Mango parameter scan"
        )

    async def _async_scan_all(self) -> None:
        for group in range(17):
            if self._closing:
                return
            async with self._io_lock:
                try:
                    self.snapshots[group] = await self._executor(self.client.read_group, group)
                    self.failed_groups.discard(group)
                    self._mark_contact()
                except MangoError:
                    self.failed_groups.add(group)
                    if self._retry_group is None:
                        self._retry_group = group
                    LOGGER.debug(
                        "Mango parameter group %s did not return complete matching descriptions", group
                    )
                self.async_set_updated_data(self.current_data())
            await asyncio.sleep(0)

    async def async_shutdown(self) -> None:
        self._closing = True
        await super().async_shutdown()
        if self._scan_task is not None and not self._scan_task.done():
            self._scan_task.cancel()
            await asyncio.gather(self._scan_task, return_exceptions=True)
        async with self._io_lock:
            await self._executor(self.client.close)
