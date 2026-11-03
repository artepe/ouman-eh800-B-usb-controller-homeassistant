"""Sensor entities for model-specific Ouman points."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_MODEL, CONF_VENDOR, CONF_ALLOW_WRITES

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    editable = entry.data.get(CONF_ALLOW_WRITES, False)
    async_add_entities([
        OumanSensor(coordinator, point)
        for point in coordinator.driver.points
        if not (editable and point.writable)
    ])

class OumanSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_name = point.name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{point.key}_sensor"
        self._attr_native_unit_of_measurement = point.unit

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.point.key)

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
            "manufacturer": entry.data[CONF_VENDOR],
            "model": entry.data[CONF_MODEL],
        }
