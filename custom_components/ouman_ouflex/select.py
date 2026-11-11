from homeassistant.components.select import SelectEntity
from .entity import OuflexEntity, setup_platform


async def async_setup_entry(hass, entry, async_add_entities):
    await setup_platform(entry, async_add_entities, 'select', OuflexSelect)


class OuflexSelect(OuflexEntity, SelectEntity):
    @property
    def options(self):
        return list(self.point.enums.values())

    @property
    def current_option(self):
        return self.point.enums.get(str(int(self.value))) if self.value is not None else None

    async def async_select_option(self, option):
        matches = [int(k) for k, v in self.point.enums.items() if v == option]
        if len(matches) != 1:
            raise ValueError('Unknown option')
        await self.set_value(matches[0])
