from homeassistant.components.sensor import SensorEntity
from .entity import OuflexEntity, setup_platform


async def async_setup_entry(hass, entry, async_add_entities):
    await setup_platform(entry, async_add_entities, 'sensor', OuflexSensor)


class OuflexSensor(OuflexEntity, SensorEntity):
    @property
    def native_value(self):
        return self.value

    @property
    def native_unit_of_measurement(self):
        return self.point.unit
