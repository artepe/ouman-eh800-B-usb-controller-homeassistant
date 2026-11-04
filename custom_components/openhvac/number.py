"""Number controls: automatically expose allowlisted EH-800B USB setpoints."""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, CONF_MODEL, CONF_VENDOR, CONF_TRANSPORT, CONF_ALLOW_WRITES,
)
from .usb_setpoints import USB_BY_KEY

_LOGGER = logging.getLogger(__name__)


def is_usb_eh800b(data) -> bool:
    """USB EH-800B has model-specific protected manual setpoint controls."""
    return (data.get(CONF_VENDOR) == "Ouman"
            and data.get(CONF_MODEL) == "EH-800B"
            and data.get(CONF_TRANSPORT) == "usb")


def writes_enabled(data) -> bool:
    # For this exact USB model a *manual* user set is permitted on the
    # allowlist from the outset, including preexisting read-only entries.
    # All other transports keep their explicit write opt-in requirement.
    return is_usb_eh800b(data) or data.get(CONF_ALLOW_WRITES, False)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    if not writes_enabled(entry.data):
        return
    async_add_entities([
        OpenHVACNumber(coordinator, point)
        for point in coordinator.driver.points
        if point.writable and point.minimum is not None and point.maximum is not None
        and (not is_usb_eh800b(entry.data) or point.key in USB_BY_KEY)
    ])


class OpenHVACNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, point):
        super().__init__(coordinator)
        self.point = point
        self._attr_name = point.name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{point.key}_number"
        self._attr_native_min_value = point.minimum
        self._attr_native_max_value = point.maximum
        self._attr_native_unit_of_measurement = point.unit
        data = coordinator.config_entry.data
        self.usb = is_usb_eh800b(data)
        if self.usb:
            # Localize only the visible name. Unique ID, address, raw
            # protocol property and HA entity_id remain untouched.
            del self._attr_name
            self._attr_has_entity_name = True
            self._attr_translation_key = f"eh800b_{point.key}"
        if self.usb:
            # Safe USB GET PROPERTY isn't validated. Current value is
            # unknown on startup. Input box is preferable to a slider
            # with a misleading guessed position.
            spec = USB_BY_KEY[point.key]
            self._attr_native_step = spec.step
            self._attr_mode = NumberMode.BOX
            self._attr_assumed_state = True
        else:
            self._attr_native_step = 10 ** (-point.decimals)

    @property
    def native_value(self):
        # USB setpoints have no safe device-side GET; a confirmed user
        # SET is the only known value. Do not conflate stale measurements
        # from a failed subsequent poll with the write acknowledgement.
        if self.usb:
            return self.coordinator.driver.last_confirmed_writes.get(self.point.key)
        return (self.coordinator.data or {}).get(self.point.key)

    @property
    def extra_state_attributes(self):
        if not self.usb:
            return None
        return {
            "usb_property_id": self.point.address,
            "value_origin": (
                "last_confirmed_user_write"
                if self.point.key in self.coordinator.driver.last_confirmed_writes
                else "unknown_until_user_write"
            ),
            "live_read_supported": False,
        }

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
            "manufacturer": entry.data[CONF_VENDOR],
            "model": entry.data[CONF_MODEL],
        }

    async def async_set_native_value(self, value):
        if not writes_enabled(self.coordinator.config_entry.data):
            raise HomeAssistantError("Remote setpoint control is disabled")
        if not self.point.minimum <= value <= self.point.maximum:
            raise HomeAssistantError("Setpoint outside allowed bounds")
        try:
            await self.coordinator.driver.async_write(self.point, float(value))
        except Exception as err:
            raise HomeAssistantError(
                f"OpenHVAC setpoint response could not be confirmed: {err}"
            ) from err
        if self.usb:
            # SET PROPERTY was confirmed exactly once by the bundled USB
            # driver. An unrelated MEASUREMENTS timeout MUST NOT turn this
            # into a false write failure or tempt the user to repeat it.
            # The regular 15-second coordinator poll will update sensors.
            self.async_write_ha_state()
            return
        try:
            await self.coordinator.async_request_refresh()
        except Exception as err:
            # A device read can fail *after* a successful write/read-back.
            # Never report that this physical write was rejected.
            _LOGGER.warning(
                "OpenHVAC setpoint command completed, but the later refresh "
                "failed for %s: %s", self.point.key, err,
            )
            self.async_write_ha_state()
            return
