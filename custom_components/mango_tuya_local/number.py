"""All captured raw parameter routes, with the one confirmed decimal scale."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import ServiceValidationError

from .entity import MangoParameterEntity
from .protocol import MangoValueError

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        MangoNumber(coordinator, p)
        for p in coordinator.profile.parameters.values()
        if p.key not in coordinator.profile.known_select_options
    )


class MangoNumber(MangoParameterEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self):
        field = self.coordinator.field(self.parameter)
        return None if field is None else field.value / self.parameter.scale

    @property
    def native_min_value(self):
        field = self.coordinator.field(self.parameter)
        return (self.parameter.lower if field is None else field.lower) / self.parameter.scale

    @property
    def native_max_value(self):
        field = self.coordinator.field(self.parameter)
        return (self.parameter.upper if field is None else field.upper) / self.parameter.scale

    @property
    def native_step(self):
        return 1 / self.parameter.scale

    async def async_set_native_value(self, value):
        try:
            raw = self.parameter.to_raw(value)
        except MangoValueError as error:
            raise ServiceValidationError("Value does not match the parameter step") from error
        await self.coordinator.async_set_raw(self.parameter, raw)
