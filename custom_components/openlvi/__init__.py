"""OpenLVI Bridge - multi-vendor heating and ventilation (experimental)."""
from datetime import timedelta
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

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "number"]

class OumanCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, driver, entry):
        super().__init__(hass, _LOGGER, name=f"OpenLVI {entry.data['vendor']} {entry.data['model']}",
                         update_interval=timedelta(seconds=15 if entry.data['transport']=="usb" else 120 if entry.data["transport"]=="mbus_serial" else 60))
        self.diagnostic_messages = []
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
                "ouflex_write_key", "ouflex_write_keys"):
        if key in entry.options:
            effective_config[key] = entry.options[key]
    driver = make_transport(hass, effective_config)
    try:
        await driver.async_connect()
        coordinator = OumanCoordinator(hass, driver, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_update_options))
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
    """Register the read-only Modbus research action; it never writes to devices."""
    from homeassistant.exceptions import ServiceValidationError
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
