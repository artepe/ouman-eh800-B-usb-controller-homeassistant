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
        ("l1_delta_t", "L1 lämpötilaero", "K"),
        ("l1_thermal_power_kw", "L1 laskettu lämpöteho", "kW"),
    ):
        if key in (coordinator.data or {}):
            entities.append(DerivedSensor(coordinator, key, name, unit))
    entities.append(DiagnosticSensor(coordinator))
    entities.append(AIGuideSensor(coordinator))
    async_add_entities(entities)

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

class DerivedSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
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
        self._attr_name = "OpenLVI diagnostiikka"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_diagnostics"

    @property
    def native_value(self):
        return "Huomio" if self.coordinator.diagnostic_messages else "Ei huomioita"

    @property
    def extra_state_attributes(self):
        return {"findings": self.coordinator.diagnostic_messages,
                "analysis": "rules only; not an AI diagnosis"}

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {"identifiers": {(DOMAIN, entry.entry_id)},
                "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}"}


class AIGuideSensor(CoordinatorEntity, SensorEntity):
    """English commentary and initial setup suggestions, never direct control."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "OpenLVI English AI guide"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_english_ai_guide"
        self._attr_icon = "mdi:robot-outline"

    @property
    def native_value(self):
        if not self.coordinator.guide:
            return "Preparing guidance"
        return ("Local AI ready" if self.coordinator.guide.last_mode.startswith("ollama:")
                else "English offline guide")

    @property
    def extra_state_attributes(self):
        guide = self.coordinator.guide
        if guide is None:
            return {"equipment_settings_changed": False}
        return {
            "english_explanation": guide.latest_answer[:2800],
            "question": guide.last_question,
            "mode": guide.last_mode,
            "error": guide.last_error,
            "equipment_settings_changed": False,
            "local_ai_url_configured": bool(guide.entry.options.get("ai_url")),
        }

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {"identifiers": {(DOMAIN, entry.entry_id)},
                "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
                "manufacturer": entry.data[CONF_VENDOR],
                "model": entry.data[CONF_MODEL]}
