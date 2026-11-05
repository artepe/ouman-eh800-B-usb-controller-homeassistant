"""Start a complete parameter scan without blocking a service action."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MangoRefreshButton(entry.runtime_data)])


class MangoRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Refresh all parameters"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_refresh_parameters"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.unique_id)})

    async def async_press(self):
        self.coordinator.async_start_scan()
