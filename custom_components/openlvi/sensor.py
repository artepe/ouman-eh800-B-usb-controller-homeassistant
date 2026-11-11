"""Sensor entities for model-specific Ouman points."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_MODEL, CONF_VENDOR, CONF_ALLOW_WRITES

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    if getattr(coordinator.driver, "discovery", False):
        async_add_entities([ModbusConnectionSensor(coordinator)])
        return
    editable = (coordinator.driver.data.get(CONF_ALLOW_WRITES, False) or
                (entry.data.get(CONF_MODEL) == "EH-800B"
                 and entry.data.get("transport") == "usb"))
    entities = [
        OumanSensor(coordinator, point)
        for point in coordinator.driver.points
        if (not (editable and point.writable)
            and point.key not in getattr(coordinator.driver, "binary_points", {}))
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
    entities.append(AIGuideSensor(coordinator))
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
        self._attr_has_entity_name = True
        self._attr_translation_key = "english_ai_guide"
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



class ModbusConnectionSensor(CoordinatorEntity, SensorEntity):
    """Expose connectivity, never invented measurements or confirmed identity."""

    _attr_has_entity_name = True
    _attr_translation_key = "modbus_connection"
    _attr_icon = "mdi:lan-connect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_modbus_connection"

    @property
    def native_value(self):
        return "tcp_connected" if (self.coordinator.data or {}).get('discovery_tcp_connected') else "tcp_disconnected"

    @property
    def extra_state_attributes(self):
        driver = self.coordinator.driver
        return {'discovery_mode': True, 'identity_confirmed': False,
                'unit_id': driver.data['unit_id'],
                'diagnostics': driver.last_diagnostics,
                'last_research': driver.last_research,
                'register_entities': 0, 'writes_enabled': False}

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {'identifiers': {(DOMAIN, entry.entry_id)},
                'name': f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
                'manufacturer': entry.data[CONF_VENDOR], 'model': entry.data[CONF_MODEL]}
