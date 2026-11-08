"""OpenLVI Bridge setup: manufacturer, model, transport, credentials."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import (
    DOMAIN, VENDOR_MODELS, CONF_VENDOR, CONF_MODEL, CONF_FIRMWARE,
    CONF_APPLICATION, CONF_TRANSPORT, CONF_HOST, CONF_PORT, CONF_BAUDRATE,
    CONF_PARITY, CONF_UNIT_ID, CONF_PROFILE, CONF_ALLOW_WRITES,
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_BACNET_LOCAL_ADDRESS,
    CONF_BACNET_DEVICE_ID, CONF_BACNET_LOCAL_INSTANCE,
)
from .profiles import profile_for
from .transport import make_transport
from .ai_guide import (CONF_AI_URL, CONF_AI_MODEL, CONF_AI_AUTO,
                       DEFAULT_MODEL, validate_local_ai_url, validate_model)

class OpenLVIBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OpenLVIAIOptionsFlow()

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_model()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_VENDOR): vol.In(tuple(VENDOR_MODELS))}),
        )

    async def async_step_model(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            model = self._data[CONF_MODEL]
            if self._data[CONF_VENDOR] == "Ouman" and model == "EH-203":
                # EH-203 has no reviewed write allowlist: force monitoring only.
                self._data[CONF_ALLOW_WRITES] = False
            if self._data[CONF_VENDOR] == "Ouman" and model in ("EH-800", "EH-800B"):
                self._data[CONF_TRANSPORT] = "http" if model == "EH-800" else "usb"
                return await self.async_step_connection()
            if self._data[CONF_VENDOR] == "Kamstrup":
                self._data[CONF_TRANSPORT] = "mbus_serial"
                self._data[CONF_ALLOW_WRITES] = False
                return await self.async_step_connection()
            return await self.async_step_transport()
        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema({
                vol.Required(CONF_MODEL): vol.In(VENDOR_MODELS[self._data[CONF_VENDOR]]),
                vol.Optional(CONF_FIRMWARE, default=""): str,
                vol.Optional(CONF_APPLICATION, default=""): str,
                vol.Optional(CONF_ALLOW_WRITES, default=False): bool,
            }),
        )

    async def async_step_transport(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_connection()
        # MODBUS 40 is an optional Modbus RTU accessory, not a built-in
        # Tehowatti Ethernet API. Only offer local RTU or a verified gateway.
        if (self._data.get(CONF_VENDOR) == "Ouman"
                and self._data.get(CONF_MODEL) == "EH-203"):
            transport_options = {
                "modbus_rtu": "MODBUS-200 / -200-DIN RS-485 (local USB adapter)",
                "modbus_tcp": "MODBUS-200 through an RTU-to-TCP gateway",
            }
            default_transport = "modbus_rtu"
        elif self._data.get(CONF_VENDOR) == "Jäspi":
            transport_options = {
                "modbus_rtu": "Modbus RTU (MODBUS 40 + RS-485 / USB)",
                "modbus_tcp": "Modbus TCP (verified RTU-to-LAN gateway only)",
            }
            default_transport = "modbus_rtu"
        else:
            transport_options = {
                "modbus_tcp": "Modbus TCP (direct or gateway)",
                "modbus_rtu": "Modbus RTU (RS-485 / USB)",
                "bacnet_ip": "BACnet/IP (read-only, UDP)",
            }
            default_transport = "modbus_tcp"
        return self.async_show_form(
            step_id="transport",
            data_schema=vol.Schema({
                vol.Required(CONF_TRANSPORT, default=default_transport): vol.In(
                    transport_options
                ),
            }),
        )

    async def async_step_connection(self, user_input=None):
        kind = self._data[CONF_TRANSPORT]
        errors = {}
        if user_input is not None:
            trial = {**self._data, **user_input}
            try:
                if kind.startswith("modbus"):
                    profile_for(
                        trial[CONF_MODEL], trial.get(CONF_FIRMWARE, ""),
                        trial.get(CONF_PROFILE, ""), trial.get(CONF_APPLICATION, ""),
                    )
                elif kind == "http" and not str(trial[CONF_URL]).startswith("http://"):
                    raise ValueError("EH-800 requires a local http:// URL")
                # Connection check is read-only. Never write to a device here.
                driver = make_transport(self.hass, trial)
                try:
                    await driver.async_connect()
                    values = await driver.async_read()
                    if not values:
                        raise ValueError("No sensor values could be read")
                finally:
                    await driver.async_close()
                identifier = ":".join(str(trial.get(k, "")) for k in (
                    CONF_VENDOR, CONF_MODEL, CONF_TRANSPORT, CONF_HOST,
                    CONF_PORT, CONF_UNIT_ID, CONF_URL, CONF_BACNET_DEVICE_ID,
                ))
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{trial[CONF_VENDOR]} {trial[CONF_MODEL]}",
                    data=trial,
                )
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
            schema = {
                vol.Required(CONF_PORT, default="/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00"): str,
            }
        elif kind == "bacnet_ip":
            schema = {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_BACNET_DEVICE_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=4194302)),
                vol.Required(CONF_BACNET_LOCAL_ADDRESS): str,
                vol.Required(CONF_BACNET_LOCAL_INSTANCE, default=400000): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=4194302)),
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        elif kind == "mbus_serial":
            schema = {
                vol.Required(CONF_PORT, default="/dev/ttyUSB0"): str,
                vol.Required(CONF_BAUDRATE, default=2400): vol.In([300, 2400, 9600, 19200]),
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=250)),
            }
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
                vol.Required(CONF_BAUDRATE, default=9600): vol.In(
                    [4800, 9600, 19200, 38400]
                    if self._data.get(CONF_MODEL) == "EH-203"
                    else [9600, 19200, 38400, 57600, 115200]),
                vol.Required(CONF_PARITY, default="N"): vol.In(["N", "E", "O"]),
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        return self.async_show_form(
            step_id="connection", data_schema=vol.Schema(schema), errors=errors,
        )


class OpenLVIAIOptionsFlow(config_entries.OptionsFlow):
    """Configure only the local AI advisor, without re-adding the controller."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                url = validate_local_ai_url(user_input.get(CONF_AI_URL, ""))
                model = validate_model(user_input.get(CONF_AI_MODEL, DEFAULT_MODEL))
                return self.async_create_entry(
                    title="", data={
                        CONF_AI_URL: url,
                        CONF_AI_MODEL: model,
                        CONF_AI_AUTO: bool(user_input.get(CONF_AI_AUTO, False)),
                    }
                )
            except ValueError:
                errors["base"] = "invalid_ai_connection"
        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_AI_URL, default=current.get(CONF_AI_URL, "")): str,
                vol.Required(CONF_AI_MODEL, default=current.get(CONF_AI_MODEL, DEFAULT_MODEL)): str,
                vol.Optional(CONF_AI_AUTO, default=current.get(CONF_AI_AUTO, False)): bool,
            }),
            errors=errors,
        )
