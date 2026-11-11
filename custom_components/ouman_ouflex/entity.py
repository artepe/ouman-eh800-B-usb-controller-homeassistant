"""Shared Ouflex entity identity, availability, and protected control calls."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from . import DOMAIN
from .coordinator import entity_platform


async def setup_platform(entry, add, platform, cls):
    coordinator = entry.runtime_data
    add([cls(coordinator, p) for p in coordinator.points
         if entity_platform(p, coordinator.can_write(p)) == platform])


class OuflexEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_name = point.name
        self._attr_unique_id = coordinator.config_entry.entry_id + '_' + point.key
        self._attr_device_info = {
            'identifiers': {(DOMAIN, coordinator.config_entry.entry_id)},
            'manufacturer': 'Ouman', 'name': 'Ouman Ouflex',
            'model': coordinator.doc['identity']['model'],
            'sw_version': coordinator.doc['identity']['firmware'],
        }

    @property
    def value(self):
        return (self.coordinator.data or {}).get(self.point.key)

    @property
    def available(self):
        return super().available and self.point.key in (self.coordinator.data or {})

    @property
    def extra_state_attributes(self):
        return dict(register=self.point.address, address_base=self.point.address_base,
                    register_area=self.point.area, datatype=self.point.kind,
                    documented_access=self.point.access,
                    write_enabled=self.coordinator.can_write(self.point))

    async def set_value(self, value):
        try:
            await self.coordinator.async_write(self.point, value)
        except Exception as err:
            raise HomeAssistantError('Ouflex write could not be confirmed: ' + str(err)) from err
