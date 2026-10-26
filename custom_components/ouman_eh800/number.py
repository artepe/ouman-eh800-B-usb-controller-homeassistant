from __future__ import annotations
import voluptuous as vol
from homeassistant.components.number import PLATFORM_SCHEMA, NumberEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.helpers.config_validation as cv
from .const import DEFAULT_PORT, DOMAIN
from .ouman import OumanUSB

CONF_PORT = "port"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string})

# id, stable object id, label, min raw, max raw, step raw, scale, initial raw
PROPS = [
    (54, "l1_supply_minimum", "L1 Supply minimum", 50, 950, 10, 10, 140),
    (55, "l1_supply_maximum", "L1 Supply maximum", 50, 950, 10, 10, 890),
    (56, "l1_p_band", "L1 P band", 2, 600, 1, 1, 250),
    (57, "l1_i_time", "L1 I time", 5, 300, 1, 1, 50),
    (58, "l1_d_time", "L1 D time", 0, 100, 1, 1, 0),
    (67, "l1_curve_minus_20c", "L1 Curve -20C", 0, 1000, 10, 10, 900),
    (69, "l1_curve_minus_10c", "L1 Curve -10C", 0, 1000, 10, 10, 700),
    (71, "l1_curve_0c", "L1 Curve 0C", 0, 1000, 10, 10, 550),
    (73, "l1_curve_plus_10c", "L1 Curve +10C", 0, 1000, 10, 10, 490),
    (75, "l1_curve_plus_20c", "L1 Curve +20C", 0, 1000, 10, 10, 180),
    (91, "l1_summer_shutoff", "L1 Summer shutoff", 5, 95, 1, 1, 24),
    (92, "l1_manual_valve_position", "L1 Manual valve position", 0, 100, 1, 1, 81),
    (126, "l1_max_supply_change_rate", "L1 Max supply change rate", 1, 50, 1, 1, 40),
    (127, "l1_supply_setpoint", "L1 Supply setpoint", 0, 950, 10, 10, 150),
    (134, "l1_fine_adjustment", "L1 Fine adjustment", -40, 40, 1, 10, 0),
]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub = OumanUSB(config[CONF_PORT])
    async_add_entities([OumanNumber(hub, *p) for p in PROPS])

class OumanNumber(NumberEntity):
    _attr_should_poll = False

    def __init__(self, hub, pid, object_id, label, pmin, pmax, step, scale, initial):
        self.hub = hub
        self.pid = pid
        self.scale = scale
        self._attr_name = f"Ouman {label}"
        self._attr_object_id = f"ouman_{object_id}"
        self._attr_unique_id = f"ouman_eh800_property_{pid}"
        self._attr_native_min_value = pmin / scale
        self._attr_native_max_value = pmax / scale
        self._attr_native_step = step / scale
        self._attr_native_value = initial / scale
        if scale == 10:
            self._attr_native_unit_of_measurement = "°C"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, "eh800_usb")},
            name="Ouman EH-800B",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )

    async def async_set_native_value(self, value):
        value = float(value)
        # Defence in depth: never send an out-of-range value to the controller,
        # even if a caller bypasses Home Assistant's service validation.
        if not self.native_min_value <= value <= self.native_max_value:
            raise HomeAssistantError(
                f"{self.name}: {value} is outside {self.native_min_value}..{self.native_max_value}"
            )
        raw = int(round(value * self.scale))
        wire_raw = raw & 0xFFFF
        _, _, _, _, returned = await self.hass.async_add_executor_job(self.hub.property, self.pid, wire_raw)
        signed_returned = returned - 65536 if returned >= 32768 else returned
        self._attr_native_value = signed_returned / self.scale
        self.async_write_ha_state()
