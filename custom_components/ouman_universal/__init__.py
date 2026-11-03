"""OpenLVI Bridge - multi-vendor heating and ventilation (experimental)."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .transport import make_transport

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "number"]

class OumanCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, driver, entry):
        super().__init__(hass, _LOGGER, name=f"OpenLVI {entry.data['vendor']} {entry.data['model']}",
                         update_interval=timedelta(seconds=15 if entry.data['transport']=="usb" else 60))
        self.driver = driver
        self.config_entry = entry

    async def _async_update_data(self):
        try:
            values = await self.driver.async_read()
            if not values:
                raise ValueError("No points responded")
            return values
        except Exception as err:
            raise UpdateFailed(f"Ouman local read failed: {err}") from err

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    driver = make_transport(hass, entry.data)
    try:
        await driver.async_connect()
        coordinator = OumanCoordinator(hass, driver, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except Exception:
        await driver.async_close()
        raise

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.driver.async_close()
        return True
    return False
