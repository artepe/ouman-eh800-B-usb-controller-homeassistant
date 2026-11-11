"""Independent experimental Ouflex integration; no built-in register guesses."""

DOMAIN = "ouman_ouflex"
PLATFORMS = ["sensor", "binary_sensor", "number", "select", "switch"]


async def async_setup_entry(hass, entry):
    from .coordinator import OuflexCoordinator
    coordinator = OuflexCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
