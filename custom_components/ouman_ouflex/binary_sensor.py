from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from .entity import OuflexEntity, setup_platform
from .pointmap import alarm_state


async def async_setup_entry(hass, entry, async_add_entities):
    await setup_platform(entry, async_add_entities, 'binary_sensor', OuflexBinary)
    async_add_entities([OuflexConnection(entry.runtime_data)])


class OuflexBinary(OuflexEntity, BinarySensorEntity):
    @property
    def is_on(self):
        if self.value is None:
            return None
        return bool(int(self.value) & 1) if self.point.entity == 'alarm' else bool(self.value)

    @property
    def extra_state_attributes(self):
        result = super().extra_state_attributes
        if self.point.entity == 'alarm' and self.value is not None:
            result.update(alarm_state(self.value, self.point.metadata.get('alarm_masks')))
        return result


class OuflexConnection(BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = 'Ouflex connection'
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_unique_id = coordinator.config_entry.entry_id + '_connection'

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def is_on(self):
        return self.coordinator.last_update_success
