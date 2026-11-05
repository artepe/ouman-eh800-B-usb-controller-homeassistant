"""Confirmed alarm option labels; unknown codes remain explicitly raw."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ServiceValidationError

from .entity import MangoParameterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        MangoSelect(coordinator, p)
        for p in coordinator.profile.parameters.values()
        if p.key in coordinator.profile.known_select_options
    )


class MangoSelect(MangoParameterEntity, SelectEntity):
    def label(self, raw):
        return self.coordinator.profile.known_select_options[self.parameter.key].get(str(raw), f"Raw {raw}")

    @property
    def options(self):
        field = self.coordinator.field(self.parameter)
        lower = self.parameter.lower if field is None else field.lower
        upper = self.parameter.upper if field is None else field.upper
        if not 0 <= upper - lower <= 16:
            return []
        return [self.label(raw) for raw in range(lower, upper + 1)]

    @property
    def current_option(self):
        field = self.coordinator.field(self.parameter)
        return None if field is None else self.label(field.value)

    async def async_select_option(self, option):
        field = self.coordinator.field(self.parameter)
        if field is None or option not in self.options:
            raise ServiceValidationError("Option is not in the fresh device bounds")
        for raw in range(field.lower, field.upper + 1):
            if self.label(raw) == option:
                await self.coordinator.async_set_raw(self.parameter, raw)
                return
        raise ServiceValidationError("Unknown option")
