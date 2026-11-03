"""Guided Ouman model and connection selection."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .const import (
    DOMAIN, MODELS, CONF_MODEL, CONF_FIRMWARE, CONF_TRANSPORT,
    CONF_HOST, CONF_PORT, CONF_BAUDRATE, CONF_UNIT_ID, CONF_PROFILE,
    CONF_ALLOW_WRITES, CONF_URL,
)
from .profiles import VERSIONS, profile_for
from .transport import make_transport

class OumanUniversalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            model = self._data[CONF_MODEL]
            if model == "EH-800":
                self._data[CONF_TRANSPORT] = "http"
                return await self.async_step_connection()
            if model == "EH-800B":
                self._data[CONF_TRANSPORT] = "usb"
                return await self.async_step_connection()
            return await self.async_step_transport()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MODEL): vol.In(MODELS),
                vol.Optional(CONF_FIRMWARE, default=""): str,
                vol.Optional(CONF_ALLOW_WRITES, default=False): bool,
            }),
        )

    async def async_step_transport(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_connection()
        return self.async_show_form(
            step_id="transport",
            data_schema=vol.Schema({
                vol.Required(CONF_TRANSPORT, default="modbus_tcp"): vol.In({
                    "modbus_tcp": "Modbus TCP (direct/gateway)",
                    "modbus_rtu": "Modbus RTU (RS-485 USB)",
                }),
            }),
        )

    async def async_step_connection(self, user_input=None):
        kind = self._data[CONF_TRANSPORT]
        model = self._data[CONF_MODEL]
        errors = {}
        if user_input is not None:
            trial = {**self._data, **user_input}
            try:
                if kind.startswith("modbus"):
                    profile_for(model, trial.get(CONF_FIRMWARE, ""), trial.get(CONF_PROFILE, ""))
                elif kind == "http" and not str(trial[CONF_URL]).startswith("http://"):
                    raise ValueError("EH-800 uses a local http:// URL")
                # Do not call any write operation during setup/validation.
                transport = make_transport(self.hass, trial)
                try:
                    await transport.async_connect()
                    values = await transport.async_read()
                    if not values:
                        raise ValueError("No valid values were returned")
                finally:
                    await transport.async_close()
                identity = ":".join(str(trial.get(k,"")) for k in
                                    (CONF_MODEL, CONF_TRANSPORT, CONF_HOST, CONF_PORT, CONF_UNIT_ID, CONF_URL))
                await self.async_set_unique_id(identity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Ouman {model}", data=trial)
            except ValueError:
                errors["base"] = "invalid_profile"
            except Exception:
                errors["base"] = "cannot_connect"
        if kind == "http":
            schema = {
                vol.Required(CONF_URL, default="http://192.168.1.100"): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            }
        elif kind == "usb":
            schema = {vol.Required(CONF_PORT, default="/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00"): str}
        elif kind == "modbus_tcp":
            schema = {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        else:
            schema = {
                vol.Required(CONF_PORT, default="/dev/ttyUSB0"): str,
                vol.Required(CONF_BAUDRATE, default=9600): vol.In([9600, 19200, 38400, 57600, 115200]),
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        return self.async_show_form(step_id="connection", data_schema=vol.Schema(schema), errors=errors)
