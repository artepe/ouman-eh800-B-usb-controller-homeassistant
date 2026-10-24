"""Opt-in, supervised EH-800B settings restore from a local known-good snapshot.

Never trigger from temperatures, sensors, startup or an automation by default.
This tool can overwrite safety-related and PID settings. Hardware validation required.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .ouman import OumanUSB

_LOGGER = logging.getLogger(__name__)

# Snapshot is intentionally fixed to the user's local HA config directory.
BACKUP_FILENAME = "ouman_properties.txt"
RECORD_RE = re.compile(
    r"^\s*PROPERTY\(\s*(\d+)\s*\):'[^']+'\([^)]*\)\s*=\s*(-?\d+)\s*$",
    re.IGNORECASE,
)
MIN_PROPERTIES = 250  # Original physical EH-800B snapshot held 269 unique IDs.
MAX_PROPERTIES = 400  # Reject an obviously unrelated or corrupted dump.
CONFIRM_PHRASE = "RESTORE EH800 SETTINGS"

SERVICE_SCHEMA = vol.Schema({
    vol.Optional("dry_run", default=True): bool,
    vol.Optional("confirm"): str,
    vol.Optional("backup_sha256"): vol.Match(r"^[0-9a-fA-F]{64}$"),
})


@dataclass(frozen=True)
class Snapshot:
    sha256: str
    properties: tuple[tuple[int, int], ...]


def load_snapshot(path: Path) -> Snapshot:
    """Parse full snapshot offline; fail closed on duplicate or malformed records."""
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    lines = data.decode("utf-8-sig", errors="strict").splitlines()
    props: dict[int, int] = {}
    for line_number, line in enumerate(lines, 1):
        match = RECORD_RE.fullmatch(line)
        if match is None:
            if "PROPERTY(" in line.upper():
                raise ValueError(f"Malformed backup property on line {line_number}")
            continue
        prop_id, raw = (int(v) for v in match.groups())
        if prop_id < 1 or prop_id > 65535:
            raise ValueError(f"Invalid property ID on line {line_number}")
        if raw < -32768 or raw > 65535:
            raise ValueError(f"Invalid raw value for property {prop_id}")
        if prop_id in props:
            raise ValueError(f"Duplicate property {prop_id} on line {line_number}")
        props[prop_id] = raw & 0xFFFF

    if not MIN_PROPERTIES <= len(props) <= MAX_PROPERTIES:
        raise ValueError(
            f"Backup has {len(props)} unique properties; expected "
            f"{MIN_PROPERTIES}-{MAX_PROPERTIES}. Do not restore incomplete data."
        )
    return Snapshot(sha256, tuple(sorted(props.items())))


async def async_setup_restore(hass: HomeAssistant, port: str) -> None:
    """Register disabled-by-default manual restore action for YAML installations."""
    hub = OumanUSB(port)
    active_task = None
    backup_path = Path(hass.config.path(BACKUP_FILENAME))

    async def restore_worker(snapshot: Snapshot) -> None:
        nonlocal active_task
        succeeded = 0
        failures = 0
        try:
            _LOGGER.warning(
                "OUMAN RESTORE START %d properties; snapshot sha256=%s; "
                "keep heating system supervised",
                len(snapshot.properties), snapshot.sha256,
            )
            for index, (prop_id, value) in enumerate(snapshot.properties, 1):
                try:
                    result = await hass.async_add_executor_job(
                        hub.property, prop_id, value
                    )
                    returned = result[4] & 0xFFFF
                    if returned != value:
                        raise ValueError(
                            f"property {prop_id} acknowledgment mismatch: "
                            f"requested {value}, received {returned}"
                        )
                    succeeded += 1
                    if index == 1 or index % 10 == 0 or index == len(snapshot.properties):
                        _LOGGER.warning(
                            "OUMAN RESTORE %d/%d property=%d OK",
                            index, len(snapshot.properties), prop_id,
                        )
                except Exception:
                    failures += 1
                    _LOGGER.exception(
                        "OUMAN RESTORE STOPPED at %d/%d property=%d; "
                        "%d successful, %d failed. Do not blindly retry. "
                        "Controller may be partially restored.",
                        index, len(snapshot.properties), prop_id,
                        succeeded, failures,
                    )
                    break  # Fail closed instead of continuing unsafe partial writes.
            _LOGGER.warning(
                "OUMAN RESTORE FINISHED: ok=%d failed=%d total=%d. "
                "Verify Ouman settings and valve operation on physical controller.",
                succeeded, failures, len(snapshot.properties),
            )
        finally:
            active_task = None

    async def handle_restore(call: ServiceCall) -> None:
        nonlocal active_task
        if active_task is not None and not active_task.done():
            raise HomeAssistantError("Ouman restore is already running")
        try:
            snapshot = await hass.async_add_executor_job(load_snapshot, backup_path)
        except (OSError, ValueError, UnicodeError) as err:
            raise HomeAssistantError(f"Cannot use Ouman backup: {err}") from err

        # Re-check after async disk I/O to prevent simultaneous restore calls.
        if active_task is not None and not active_task.done():
            raise HomeAssistantError("Ouman restore is already running")

        if call.data.get("dry_run", True):
            _LOGGER.warning(
                "OUMAN RESTORE DRY RUN: %d properties; sha256=%s; "
                "NO USB writes. Confirm this is a known-good backup from "
                "this exact EH-800B before any real restore.",
                len(snapshot.properties), snapshot.sha256,
            )
            return

        if call.data.get("confirm") != CONFIRM_PHRASE:
            raise HomeAssistantError(
                f"Real restore requires confirm: {CONFIRM_PHRASE!r}"
            )
        if call.data.get("backup_sha256", "").lower() != snapshot.sha256:
            raise HomeAssistantError(
                "Backup hash mismatch. Run dry_run first, verify the file "
                "and explicitly confirm its SHA-256. No values were written."
            )

        active_task = hass.async_create_task(restore_worker(snapshot))

    hass.services.async_register(
        DOMAIN, "restore_original", handle_restore, schema=SERVICE_SCHEMA,
    )
