"""OpenLVI Bridge - multi-vendor heating and ventilation (experimental)."""
from datetime import timedelta
from time import monotonic
import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (DOMAIN, CONF_ALLOW_WRITES, CONF_PROFILE, CONF_DISCOVERY,
                    CONF_PROFILE_CONFIRMED, CONF_UNIT_ID)
from .transport import make_transport
from .diagnostics import derive_plant_metrics, diagnostic_notes
from .engineering import derive_cop_metrics
from .ai_guide import (OpenLVIGuide, CONF_AI_AUTO, CONF_AI_URL, REVIEW_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "number", "button"]

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
    # Options can enable/disable allowlisted writes without re-adding a device.
    # Never persist an enabled mode into the base config during discovery.
    effective_config = dict(entry.data)
    for key in (CONF_PROFILE, CONF_DISCOVERY, CONF_PROFILE_CONFIRMED, CONF_UNIT_ID):
        if key in entry.options:
            effective_config[key] = entry.options[key]
    effective_config[CONF_ALLOW_WRITES] = bool(entry.options.get(
        CONF_ALLOW_WRITES, entry.data.get(CONF_ALLOW_WRITES, False)))
    # Retain per-device Ouflex write review settings in the existing bridge.
    for key in ("ouflex_write_enabled", "ouflex_write_isolated",
                "ouflex_write_reviewed", "ouflex_write_digest",
                "ouflex_write_key"):
        if key in entry.options:
            effective_config[key] = entry.options[key]
    driver = make_transport(hass, effective_config)
    try:
        await driver.async_connect()
        coordinator = OumanCoordinator(hass, driver, entry)
        await coordinator.async_config_entry_first_refresh()
        if not getattr(driver, "discovery", False):
            coordinator.guide = OpenLVIGuide(hass, entry, coordinator)
            coordinator.guide.baseline(coordinator.data or {})
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_update_options))
        if (coordinator.guide and entry.options.get(CONF_AI_AUTO, False)
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
    from .modbus_research import research

    async def research_registers(call):
        entry = hass.config_entries.async_get_entry(call.data['config_entry_id'])
        runtime = getattr(entry, 'runtime_data', None) if entry else None
        if entry is None or entry.domain != DOMAIN or runtime is None:
            raise ServiceValidationError("Choose a loaded OpenLVI config entry")
        if runtime.driver.data.get('transport') != 'modbus_tcp':
            raise ServiceValidationError("Research requires Modbus TCP")
        function = call.data['function']
        if function != 43 and not call.data.get('documented', False):
            raise ServiceValidationError("Confirm the register address source with documented: true")
        try:
            results = await research(
                runtime.driver, call.data['unit_ids'], function=function,
                address=call.data.get('address'), address_base=call.data['address_base'],
                count=call.data['count'])
        except (ValueError, TypeError) as err:
            raise ServiceValidationError(str(err)) from err
        runtime.async_update_listeners()
        return {'results': results, 'controller_settings_changed': False}

    if not hass.services.has_service(DOMAIN, 'research_registers'):
        hass.services.async_register(
            DOMAIN, 'research_registers', research_registers,
            schema=vol.Schema({
                vol.Required('config_entry_id'): str,
                vol.Required('unit_ids', default='1'): str,
                vol.Required('function', default=43): vol.All(vol.Coerce(int), vol.In((3, 4, 43))),
                vol.Optional('address'): vol.All(vol.Coerce(int), vol.Range(min=0, max=65536)),
                vol.Required('address_base', default=0): vol.All(vol.Coerce(int), vol.In((0, 1))),
                vol.Required('count', default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
                vol.Optional('documented', default=False): bool,
            }), supports_response=SupportsResponse.ONLY,
        )
    return True

