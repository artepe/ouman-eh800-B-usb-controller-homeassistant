from homeassistant.components.switch import SwitchEntity
from .entity import OuflexEntity, setup_platform


async def async_setup_entry(hass, entry, async_add_entities):
    await setup_platform(entry, async_add_entities, 'switch', OuflexSwitch)


class OuflexSwitch(OuflexEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.value == 1 if self.value is not None else None

    async def async_turn_on(self, **kwargs):
        await self.set_value(1)

    async def async_turn_off(self, **kwargs):
        await self.set_value(0)
