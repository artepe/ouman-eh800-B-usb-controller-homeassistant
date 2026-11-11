"""OpenLVI Bridge setup: manufacturer, model, transport, credentials."""
import json

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import (
    DOMAIN, VENDOR_MODELS, CONF_VENDOR, CONF_MODEL, CONF_FIRMWARE,
    CONF_APPLICATION, CONF_TRANSPORT, CONF_HOST, CONF_PORT, CONF_BAUDRATE,
    CONF_PARITY, CONF_UNIT_ID, CONF_PROFILE, CONF_ALLOW_WRITES,
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_BACNET_LOCAL_ADDRESS,
    CONF_BACNET_DEVICE_ID, CONF_BACNET_LOCAL_INSTANCE,
    CONF_DISCOVERY, CONF_PROFILE_CONFIRMED,
)
from .profiles import profile_for
from .transport import make_transport
from .modbus_research import probe, research, unit_ids, read_parameters
from .ai_guide import (CONF_AI_URL, CONF_AI_MODEL, CONF_AI_AUTO,
                       DEFAULT_MODEL, validate_local_ai_url, validate_model)

class OpenLVIBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OpenLVIAIOptionsFlow()

    def __init__(self):
        self._data = {}
        self._pending = None
        self._diagnostics = {}

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
            if self._data[CONF_VENDOR] == "Ouman" and model in ("EH-800", "EH-800B"):
                self._data[CONF_TRANSPORT] = "http" if model == "EH-800" else "usb"
                return await self.async_step_connection()
            if model == "MCX (site-programmed)" and self._data[CONF_VENDOR] == "Danfoss":
                # MCX is application-programmed; never grant writes or assume a map.
                self._data[CONF_ALLOW_WRITES] = False
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
        if self._data.get(CONF_MODEL) == "MCX (site-programmed)":
            # Only application-confirmed RS485 Modbus RTU, or a verified gateway.
            transport_options = {
                "modbus_rtu": "Modbus RTU (confirmed RS485 port)",
                "modbus_tcp": "Modbus TCP (verified RS485-to-TCP gateway only)",
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
                discovery = kind == "modbus_tcp" and trial.get(CONF_DISCOVERY, False)
                if trial.get(CONF_DISCOVERY) and kind != "modbus_tcp":
                    raise ValueError("Discovery Mode requires Modbus TCP")
                if discovery:
                    trial[CONF_ALLOW_WRITES] = False
                    trial[CONF_PROFILE] = ""
                    self._diagnostics = await probe(trial[CONF_HOST], trial[CONF_PORT], trial[CONF_UNIT_ID])
                    if not self._diagnostics['tcp_connected']:
                        errors["base"] = "cannot_connect_tcp"
                    else:
                        trial['discovery_diagnostics'] = self._diagnostics
                        self._pending = trial
                        return await self.async_step_discovery_result()
                else:
                    if kind.startswith("modbus"):
                        profile_for(
                            trial[CONF_MODEL], trial.get(CONF_FIRMWARE, ""),
                            trial.get(CONF_PROFILE, ""), trial.get(CONF_APPLICATION, ""),
                        )
                        if (trial[CONF_MODEL].startswith("Ouflex")
                                and not trial.get(CONF_PROFILE_CONFIRMED, False)):
                            raise ValueError("Confirm register meanings before creating entities")
                    elif kind == "http" and not str(trial[CONF_URL]).startswith("http://"):
                        raise ValueError("EH-800 requires a local http:// URL")
                    driver = make_transport(self.hass, trial)
                    try:
                        await driver.async_connect()
                        values = await driver.async_read()
                        if not values:
                            raise ConnectionError("No sensor values could be read")
                    finally:
                        await driver.async_close()
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_profile"
            except Exception:
                errors["base"] = "cannot_connect"
            if not errors:
                return await self._async_finish(trial)

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
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
                vol.Optional(CONF_DISCOVERY, default=self._data.get(CONF_MODEL, "").startswith("Ouflex")): bool,
                vol.Optional(CONF_PROFILE_CONFIRMED, default=False): bool,
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        else:
            schema = {
                vol.Required(CONF_PORT, default="/dev/ttyUSB0"): str,
                vol.Required(CONF_BAUDRATE, default=9600): vol.In([9600, 19200, 38400, 57600, 115200]),
                vol.Required(CONF_PARITY, default="N"): vol.In(["N", "E", "O"]),
                vol.Optional(CONF_PROFILE_CONFIRMED, default=False): bool,
                vol.Required(CONF_UNIT_ID, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
                vol.Optional(CONF_PROFILE, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)),
            }
        return self.async_show_form(
            step_id="connection", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={"diagnostics": json.dumps(self._diagnostics, ensure_ascii=False)},
        )

    async def async_step_discovery_result(self, user_input=None):
        if self._pending is None:
            return await self.async_step_connection()
        if user_input is not None:
            return await self._async_finish(self._pending)
        return self.async_show_form(
            step_id="discovery_result", data_schema=vol.Schema({}),
            description_placeholders={"diagnostics": json.dumps(self._diagnostics, ensure_ascii=False, indent=2)},
        )

    async def _async_finish(self, trial):
        identifier = ":".join(str(trial.get(k, "")) for k in (
            CONF_VENDOR, CONF_MODEL, CONF_TRANSPORT, CONF_HOST,
            CONF_PORT, CONF_UNIT_ID, CONF_URL, CONF_BACNET_DEVICE_ID,
        ))
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{trial[CONF_VENDOR]} {trial[CONF_MODEL]}", data=trial,
        )


class OpenLVIAIOptionsFlow(config_entries.OptionsFlow):
    """Local advisor, confirmed register map and manual read-only research."""

    async def async_step_init(self, user_input=None):
        if self.config_entry.data.get(CONF_TRANSPORT) == "modbus_tcp":
            menus = ["register_map", "research", "advisor"]
            if self.config_entry.data.get(CONF_MODEL) == "Ouflex":
                menus.insert(0, "ouflex_write")
            return self.async_show_menu(step_id="init", menu_options=menus)
        return await self.async_step_advisor(user_input)

    async def async_step_ouflex_write(self, user_input=None):
        """Choose multiple reviewed setpoints for an isolated Ouflex test rig."""
        from custom_components.ouman_ouflex.ftp_map import fetch_application_map
        from custom_components.ouman_ouflex.pointmap import load_map, map_digest
        from .ouflex_write import candidates, selected_keys

        try:
            doc = await self.hass.async_add_executor_job(
                fetch_application_map, self.config_entry.data[CONF_HOST])
            _, points = load_map(json.dumps(doc, ensure_ascii=False))
            eligible = sorted(candidates(points), key=lambda p: p.name.casefold())
            if not eligible:
                raise ValueError("No bounded numeric setpoint candidates")
            digest = map_digest(doc)
        except Exception:
            return self.async_abort(reason="cannot_connect")

        valid_keys = {p.key for p in eligible}
        current = self.config_entry.options
        errors = {}
        if user_input is not None:
            enabled = user_input.get("ouflex_write_enabled") is True
            selected = user_input.get("ouflex_write_keys", [])
            isolated = user_input.get("ouflex_write_isolated") is True
            reviewed = user_input.get("ouflex_write_reviewed") is True
            if (enabled and
                    (not isinstance(selected, list)
                     or not selected
                     or len(selected) > 64
                     or len(set(selected)) != len(selected)
                     or any(key not in valid_keys for key in selected)
                     or not isolated or not reviewed)):
                errors["base"] = "invalid_profile"
            else:
                updated = {
                    **current,
                    "ouflex_write_enabled": enabled,
                    "ouflex_write_keys": selected if enabled else [],
                    # Clear legacy single-key choice to avoid ambiguous state.
                    "ouflex_write_key": "",
                    "ouflex_write_digest": digest if enabled else "",
                    "ouflex_write_isolated": isolated if enabled else False,
                    "ouflex_write_reviewed": reviewed if enabled else False,
                    CONF_ALLOW_WRITES: False,
                }
                return self.async_create_entry(title="", data=updated)

        defaults = [key for key in selected_keys(current) if key in valid_keys]
        return self.async_show_form(
            step_id="ouflex_write",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required(
                    "ouflex_write_enabled",
                    default=current.get("ouflex_write_enabled", False),
                ): bool,
                vol.Optional("ouflex_write_keys", default=defaults):
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            multiple=True,
                            options=[
                                {
                                    "value": p.key,
                                    "label": (
                                        f"{p.name} | Modbus {p.address} | "
                                        f"{p.minimum}–{p.maximum} {p.unit or ''}"
                                    ),
                                }
                                for p in eligible
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                vol.Required("ouflex_write_isolated", default=False): bool,
                vol.Required("ouflex_write_reviewed", default=False): bool,
            }),
        )

    async def async_step_register_map(self, user_input=None):
        current = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                discovery = user_input.get(CONF_DISCOVERY, False)
                if not discovery:
                    profile_for(current[CONF_MODEL], current.get(CONF_FIRMWARE, ""),
                                user_input.get(CONF_PROFILE, ""), current.get(CONF_APPLICATION, ""))
                    if not user_input.get(CONF_PROFILE_CONFIRMED, False):
                        raise ValueError("Confirm register meanings first")
                updated = {**self.config_entry.options, **user_input}
                if discovery:
                    updated[CONF_ALLOW_WRITES] = False
                return self.async_create_entry(title="", data=updated)
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_profile"
        return self.async_show_form(step_id="register_map", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_DISCOVERY, default=current.get(CONF_DISCOVERY, False)): bool,
            vol.Optional(CONF_PROFILE, default=current.get(CONF_PROFILE, "")): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)),
            vol.Required(CONF_UNIT_ID, default=current.get(CONF_UNIT_ID, 1)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Optional(CONF_PROFILE_CONFIRMED, default=current.get(CONF_PROFILE_CONFIRMED, False)): bool,
        }))

    async def async_step_research(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                units = user_input['unit_ids']
                unit_ids(units)
                function = user_input['function']
                if function != 43:
                    if not user_input.get('documented', False):
                        raise ValueError("Confirm address source before reading")
                    read_parameters(user_input.get('address'), user_input['address_base'],
                                    user_input['count'], function)
                runtime = getattr(self.config_entry, 'runtime_data', None)
                if runtime is None:
                    errors['base'] = 'entry_not_loaded'
                else:
                    self._research_results = await research(
                        runtime.driver, units, function=function, address=user_input.get('address'),
                        address_base=user_input['address_base'], count=user_input['count'])
                    runtime.async_update_listeners()
                    return await self.async_step_research_result()
            except (ValueError, KeyError, TypeError):
                errors['base'] = 'invalid_research'
        return self.async_show_form(step_id="research", errors=errors, data_schema=vol.Schema({
            vol.Required('unit_ids', default=str(self.config_entry.options.get(
                CONF_UNIT_ID, self.config_entry.data.get(CONF_UNIT_ID, 1)))): str,
            vol.Required('function', default=43): vol.All(vol.Coerce(int), vol.In({43: '43/14 Device identification',
                                                        3: '03 Holding registers', 4: '04 Input registers'})),
            vol.Optional('address'): vol.All(vol.Coerce(int), vol.Range(min=0, max=65536)),
            vol.Required('address_base', default=0): vol.All(vol.Coerce(int), vol.In({0: '0-based PDU', 1: '1-based document address'})),
            vol.Required('count', default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
            vol.Optional('documented', default=False): bool,
        }))

    async def async_step_research_result(self, user_input=None):
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(step_id="research_result", data_schema=vol.Schema({}),
            description_placeholders={'diagnostics': json.dumps(self._research_results, ensure_ascii=False, indent=2)})


    async def async_step_advisor(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                url = validate_local_ai_url(user_input.get(CONF_AI_URL, ""))
                model = validate_model(user_input.get(CONF_AI_MODEL, DEFAULT_MODEL))
                current_discovery = self.config_entry.options.get(
                    CONF_DISCOVERY, self.config_entry.data.get(CONF_DISCOVERY, False))
                return self.async_create_entry(
                    title="", data={
                        **self.config_entry.options,
                        CONF_AI_URL: url,
                        CONF_AI_MODEL: model,
                        CONF_AI_AUTO: bool(user_input.get(CONF_AI_AUTO, False)),
                        CONF_ALLOW_WRITES: bool(user_input.get(CONF_ALLOW_WRITES, False)) and not current_discovery,
                    }
                )
            except ValueError:
                errors["base"] = "invalid_ai_connection"
        current = self.config_entry.options
        return self.async_show_form(
            step_id="advisor",
            data_schema=vol.Schema({
                vol.Optional(CONF_AI_URL, default=current.get(CONF_AI_URL, "")): str,
                vol.Required(CONF_AI_MODEL, default=current.get(CONF_AI_MODEL, DEFAULT_MODEL)): str,
                vol.Optional(CONF_AI_AUTO, default=current.get(CONF_AI_AUTO, False)): bool,
                vol.Optional(CONF_ALLOW_WRITES, default=current.get(
                    CONF_ALLOW_WRITES, self.config_entry.data.get(CONF_ALLOW_WRITES, False))): bool,
            }),
            errors=errors,
        )

