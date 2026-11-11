"""Ouflex digital-state and alarm entities for Open HVAC Bridge."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_MODEL, CONF_VENDOR


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    driver = coordinator.driver
    if not getattr(driver, "is_ouflex_native", False):
        return
    async_add_entities(
        OuflexDigital(coordinator, native_point)
        for native_point in driver.binary_points.values()
    )


class OuflexDigital(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, native_point):
        super().__init__(coordinator)
        self.point = native_point
        self._attr_name = native_point.name
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{native_point.key}_binary")
        if native_point.entity == "alarm":
            self._attr_icon = "mdi:alarm-light-outline"

    @property
    def available(self):
        return (super().available and
                self.point.key in (self.coordinator.data or {}))

    @property
    def is_on(self):
        value = (self.coordinator.data or {}).get(self.point.key)
        if value is None:
            return None
        raw = int(value)
        if self.point.entity == "alarm":
            masks = self.point.metadata.get("alarm_masks") or {}
            return bool(raw & int(masks.get("active", 1)))
        return bool(raw)

    @property
    def extra_state_attributes(self):
        point = self.point
        result = {
            "register_address": point.address,
            "register_address_base": point.address_base,
            "raw_value": (self.coordinator.data or {}).get(point.key),
            "read_only": True,
        }
        if point.entity == "alarm":
            masks = point.metadata.get("alarm_masks") or {}
            raw = int(result["raw_value"] or 0)
            for label in ("unacknowledged", "priority", "group"):
                mask = int(masks.get(label, 0))
                if mask:
                    shift = (mask & -mask).bit_length() - 1
                    result[label] = (
                        bool(raw & mask) if label == "unacknowledged"
                        else (raw & mask) >> shift)
        return result

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
            "manufacturer": entry.data[CONF_VENDOR],
            "model": entry.data[CONF_MODEL],
        }
