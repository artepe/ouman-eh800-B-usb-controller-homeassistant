"""Observed DP105 temperatures and parameter scan progress."""

import time

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        MangoSensor(entry.runtime_data, key)
        for key in ("current_temperature", "target_temperature", "parameters_read")
    )


class MangoSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{key}"
        self._attr_name = {
            "current_temperature": "Current temperature",
            "target_temperature": "Target temperature",
            "parameters_read": "Parameters read",
        }[key]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.unique_id)})
        if key == "parameters_read":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self):
        if not self.coordinator.last_update_success or self.coordinator.connection_state == "offline":
            return False
        if self.key == "parameters_read":
            return True
        data = self.coordinator.data
        return (
            self.key in data["temperatures"]
            and time.time() - data["temperature_received_at"] <= self.coordinator.interval * 3 + 10
        )

    @property
    def extra_state_attributes(self):
        return {
            "communication_state": self.coordinator.connection_state,
            "data_received_at": None
            if self.key == "parameters_read"
            else self.coordinator.data["temperature_received_at"],
        }

    @property
    def native_value(self):
        if self.key == "parameters_read":
            return sum(len(s.fields) for s in self.coordinator.snapshots.values())
        return self.coordinator.data["temperatures"].get(self.key)
