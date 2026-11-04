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

# id, stable object id, label, min raw, max raw, step raw, scale
# v0.1.3: PID 56/57/58 (P band, I time, D time) and manual valve position 92
# are no longer exposed. Changing them on a live plant coincided with
# abnormal valve behaviour (docs/PID_KNOWN_ISSUES.md).
FORBIDDEN_PROPERTY_IDS = frozenset({56, 57, 58, 92})
PROPS = [
    (54, "l1_supply_minimum", "L1 Supply minimum", 50, 950, 10, 10),
    (55, "l1_supply_maximum", "L1 Supply maximum", 50, 950, 10, 10),
    (67, "l1_curve_minus_20c", "L1 Curve -20C", 0, 1000, 10, 10),
    (69, "l1_curve_minus_10c", "L1 Curve -10C", 0, 1000, 10, 10),
    (71, "l1_curve_0c", "L1 Curve 0C", 0, 1000, 10, 10),
    (73, "l1_curve_plus_10c", "L1 Curve +10C", 0, 1000, 10, 10),
    (75, "l1_curve_plus_20c", "L1 Curve +20C", 0, 1000, 10, 10),
    (91, "l1_summer_shutoff", "L1 Summer shutoff", 5, 95, 1, 1),
    (126, "l1_max_supply_change_rate", "L1 Max supply change rate", 1, 50, 1, 1),
    (127, "l1_supply_setpoint", "L1 Supply setpoint", 0, 950, 10, 10),
    (134, "l1_fine_adjustment", "L1 Fine adjustment", -40, 40, 1, 10),
]
if {p[0] for p in PROPS} & FORBIDDEN_PROPERTY_IDS:
    raise RuntimeError("PID/manual valve properties must not be exposed")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub = OumanUSB(config[CONF_PORT])
    async_add_entities([OumanNumber(hub, *p) for p in PROPS])

class OumanNumber(NumberEntity):
    _attr_should_poll = False

    def __init__(self, hub, pid, object_id, label, pmin, pmax, step, scale):
        self.hub = hub
        self.pid = pid
        self.scale = scale
        self._attr_name = f"Ouman {label}"
        self._attr_object_id = f"ouman_{object_id}"
        self._attr_unique_id = f"ouman_eh800_property_{pid}"
        self._attr_native_min_value = pmin / scale
        self._attr_native_max_value = pmax / scale
        self._attr_native_step = step / scale
        # No safe USB read exists for these properties. Show unknown until a
        # confirmed write instead of placeholder numbers that look real.
        self._attr_native_value = None
        self._attr_assumed_state = True
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
