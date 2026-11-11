from homeassistant.components.number import NumberEntity, NumberMode
from .entity import OuflexEntity, setup_platform


async def async_setup_entry(hass, entry, async_add_entities):
    await setup_platform(entry, async_add_entities, 'number', OuflexNumber)


class OuflexNumber(OuflexEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self):
        return self.value

    @property
    def native_min_value(self):
        return self.point.minimum

    @property
    def native_max_value(self):
        return self.point.maximum

    @property
    def native_step(self):
        return 10 ** -self.point.decimals

    @property
    def native_unit_of_measurement(self):
        return self.point.unit

    async def async_set_native_value(self, value):
        await self.set_value(value)
