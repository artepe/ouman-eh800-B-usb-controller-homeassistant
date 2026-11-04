"""OpenLVI Bridge - multi-vendor heating and ventilation (experimental)."""
from datetime import timedelta
from time import monotonic
import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .transport import is_auth_error, make_transport
from .diagnostics import derive_plant_metrics, diagnostic_notes
from .engineering import derive_cop_metrics
from .ai_guide import (OpenLVIGuide, CONF_AI_AUTO, CONF_AI_URL, REVIEW_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number", "button"]

class OumanCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, driver, entry):
        super().__init__(hass, _LOGGER, name=f"OpenLVI {entry.data['vendor']} {entry.data['model']}",
                         update_interval=timedelta(seconds=15 if entry.data['transport']=="usb" else 120 if entry.data["transport"]=="mbus_serial" else 60))
        self.diagnostic_messages = []
        self.guide = None
        self.driver = driver
        self.config_entry = entry

    async def _async_update_data(self):
        try:
            values = await self.driver.async_read()
            if not values:
                raise ValueError("No points responded")
            values.update(derive_plant_metrics(values))
            values.update(derive_cop_metrics(values))
            self.diagnostic_messages = diagnostic_notes(values)
            if self.guide:
                self.guide.baseline(values)
                if (self.config_entry.options.get(CONF_AI_AUTO, False)
                    and self.config_entry.options.get(CONF_AI_URL, "").strip()
                    and not self.guide.in_progress
                    and monotonic() - self.guide.last_auto_review > REVIEW_INTERVAL_SECONDS):
                    self.guide.last_auto_review = monotonic()
                    self.config_entry.async_create_background_task(
                        self.hass, self.guide.review(),
                        f"OpenLVI English review {self.config_entry.entry_id}")
            return values
        except Exception as err:
            raise UpdateFailed(f"OpenLVI local read failed: {err}") from err

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    try:
        driver = make_transport(hass, entry.data)
    except ImportError as err:
        raise ConfigEntryError(
            "EH-800B USB needs the custom_components/ouman_eh800 folder "
            f"(protocol reader) next to openlvi: {err}"
        ) from err
    except (ValueError, KeyError) as err:
        # A stored profile/firmware/address that no longer validates cannot
        # be fixed by retrying; show it as a configuration error instead.
        raise ConfigEntryError(f"Invalid OpenLVI configuration: {err}") from err
    try:
        await driver.async_connect()
    except Exception as err:
        await driver.async_close()
        if is_auth_error(err):
            raise ConfigEntryError(
                "The controller rejected the stored username or password"
            ) from err
        # Typical after a power cut: HA boots before the controller or
        # Modbus gateway. ConfigEntryNotReady makes HA retry with back-off
        # instead of leaving the entry failed until a manual reload.
        raise ConfigEntryNotReady(f"Controller not reachable yet: {err}") from err
    try:
        coordinator = OumanCoordinator(hass, driver, entry)
        await coordinator.async_config_entry_first_refresh()
        coordinator.guide = OpenLVIGuide(hass, entry, coordinator)
        coordinator.guide.baseline(coordinator.data or {})
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_update_options))
        if (entry.options.get(CONF_AI_AUTO, False)
            and entry.options.get(CONF_AI_URL, "").strip()):
            coordinator.guide.last_auto_review = monotonic()
            entry.async_create_background_task(
                hass, coordinator.guide.review(), "OpenLVI first local AI review")
        return True
    except Exception:
        await driver.async_close()
        raise

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.driver.async_close()
        return True
    return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register an advisory-only question service; does not write to devices."""
    from homeassistant.exceptions import ServiceValidationError

    async def ask_assistant(call):
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None and getattr(e.runtime_data, "guide", None)
        ]
        requested = call.data.get("config_entry_id", "")
        if requested:
            entries = [e for e in entries if e.entry_id == requested]
        if len(entries) != 1:
            raise ServiceValidationError(
                "Select a valid OpenLVI config_entry_id (required if multiple devices exist)"
            )
        entry = entries[0]
        answer = await entry.runtime_data.guide.ask(call.data["question"])
        return {
            "answer": answer,
            "model": entry.data.get("model", ""),
            "inference": entry.runtime_data.guide.last_mode,
            "controller_settings_changed": False,
        }

    if not hass.services.has_service(DOMAIN, "ask_assistant"):
        hass.services.async_register(
            DOMAIN, "ask_assistant", ask_assistant,
            schema=vol.Schema({
                vol.Required("question"): vol.All(str, vol.Length(min=1, max=400)),
                vol.Optional("config_entry_id", default=""): str,
            }),
            supports_response=SupportsResponse.ONLY,
        )
    return True
