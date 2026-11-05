"""Mango Tuya Local parameter integration."""

from homeassistant.const import CONF_HOST, Platform

from .client import MangoClient
from .const import CONF_DEVICE_ID, CONF_LOCAL_KEY
from .coordinator import MangoCoordinator
from .dashboard import async_setup_dashboard
from .protocol import Profile

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass, config):
    await async_setup_dashboard(hass)
    return True


async def async_setup_entry(hass, entry):
    profile = await hass.async_add_executor_job(Profile.load)
    client = MangoClient(
        entry.data[CONF_HOST], entry.data[CONF_DEVICE_ID], entry.data[CONF_LOCAL_KEY], profile
    )
    coordinator = MangoCoordinator(hass, entry, profile, client)
    coordinator.descriptions = hass.data["mango_tuya_local"]["catalog"]["parameters"]
    entry.runtime_data = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    coordinator.async_start_scan()
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        return True
    return False
