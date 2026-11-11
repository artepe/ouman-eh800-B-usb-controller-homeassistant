"""Sensor entities for model-specific Ouman points."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_MODEL, CONF_VENDOR, CONF_ALLOW_WRITES

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    editable = (entry.data.get(CONF_ALLOW_WRITES, False) or
                (entry.data.get(CONF_MODEL) == "EH-800B"
                 and entry.data.get("transport") == "usb"))
    entities = [
        OumanSensor(coordinator, point)
        for point in coordinator.driver.points
        if not (editable and point.writable)
    ]
    for key, name, unit in (
        ("l1_delta_t", "L1 temperature difference", "K"),
        ("l1_thermal_power_kw", "L1 estimated thermal power", "kW"),
        ("water_heating_power_kw", "Water-side heating output", "kW"),
        ("system_heating_cop", "Whole-system heating COP", None),
        ("water_compressor_heating_cop", "Water-side compressor heating COP", None),
        ("refrigerant_cycle_heating_cop_estimate", "Refrigerant thermodynamic heating COP estimate", None),
        ("refrigerant_heating_power_kw", "Refrigerant condenser heat output", "kW"),
        ("refrigerant_compressor_heating_cop", "Refrigerant compressor electrical heating COP", None),
    ):
        if key in (coordinator.data or {}):
            entities.append(DerivedSensor(coordinator, key, name, unit))
    entities.append(DiagnosticSensor(coordinator))
    async_add_entities(entities)

class OumanSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_name = point.name
        # Stable unique IDs and point keys never change. Only the displayed
        # Ouman USB names are localized by Home Assistant per user language.
        if (coordinator.config_entry.data.get(CONF_VENDOR) == "Ouman"
                and coordinator.config_entry.data.get(CONF_MODEL) == "EH-800B"
                and coordinator.config_entry.data.get("transport") == "usb"):
            del self._attr_name
            self._attr_has_entity_name = True
            self._attr_translation_key = f"eh800b_{point.key}"
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

class DerivedSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit):
        super().__init__(coordinator)
        self.key = key
        self._attr_has_entity_name = True
        self._attr_translation_key = f"derived_{key}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_derived_{key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {"identifiers": {(DOMAIN, entry.entry_id)},
                "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}"}


class DiagnosticSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = "diagnostics"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_diagnostics"

    @property
    def native_value(self):
        return "Review needed" if self.coordinator.diagnostic_messages else "No findings"

    @property
    def extra_state_attributes(self):
        return {"findings": self.coordinator.diagnostic_messages,
                "analysis": "rule-based checks only"}

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {"identifiers": {(DOMAIN, entry.entry_id)},
                "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}"}
