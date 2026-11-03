"""Conservative operator-enabled setpoint controls."""
from homeassistant.components.number import NumberEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_MODEL, CONF_ALLOW_WRITES

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    if not entry.data.get(CONF_ALLOW_WRITES, False):
        return
    async_add_entities([
        OumanNumber(coordinator, point)
        for point in coordinator.driver.points
        if point.writable and point.minimum is not None and point.maximum is not None
    ])

class OumanNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_name = f"Ouman {point.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{point.key}_number"
        self._attr_native_min_value = point.minimum
        self._attr_native_max_value = point.maximum
        self._attr_native_step = 10 ** (-point.decimals)
        self._attr_native_unit_of_measurement = point.unit

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.point.key)

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Ouman {entry.data[CONF_MODEL]}",
            "manufacturer": "Ouman",
            "model": entry.data[CONF_MODEL],
        }

    async def async_set_native_value(self, value):
        if not self.coordinator.config_entry.data.get(CONF_ALLOW_WRITES):
            raise HomeAssistantError("Writes are disabled")
        if not self.point.minimum <= value <= self.point.maximum:
            raise HomeAssistantError("Value outside Ouman documented limits")
        try:
            await self.coordinator.driver.async_write(self.point, float(value))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to set Ouman value: {err}") from err
