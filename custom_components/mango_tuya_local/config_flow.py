"""UI setup with manual credentials or the owner's local Pi session export."""

from __future__ import annotations

import json
from pathlib import Path

import probatio as schema
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client import MangoClient
from .const import (
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    NAME,
)
from .executor import async_call
from .protocol import MangoError, Profile

CREDENTIAL_FILE = "mango_tuya_local_credentials.json"


def load_pi_credentials(path: str):
    data = json.loads(Path(path).read_text())
    if data.get("format") != "mango_tuya_local_credentials_v1":
        raise ValueError("invalid_credentials_file")
    return {key: data[key] for key in (CONF_HOST, CONF_DEVICE_ID, CONF_LOCAL_KEY)}


def validate_local(data):
    host, device_id, key = data[CONF_HOST].strip(), data[CONF_DEVICE_ID].strip(), data[CONF_LOCAL_KEY]
    if not host or "://" in host or not device_id or len(key.encode()) != 16:
        raise ValueError("invalid_credentials")
    client = MangoClient(host, device_id, key, Profile.load())
    try:
        client.validate_profile()
    finally:
        client.close()
    return {CONF_HOST: host, CONF_DEVICE_ID: device_id, CONF_LOCAL_KEY: key}


class MangoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["pi", "manual"])

    async def _async_finish(self, data, title):
        try:
            clean = await async_call(self.hass, validate_local, data)
        except ValueError:
            return None, {"base": "invalid_credentials"}
        except MangoError:
            return None, {"base": "cannot_connect"}
        except Exception:
            return None, {"base": "cannot_connect"}
        await self.async_set_unique_id(clean[CONF_DEVICE_ID])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=clean), {}

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            result, errors = await self._async_finish(user_input, user_input.get(CONF_NAME, NAME))
            if result is not None:
                return result
        return self.async_show_form(
            step_id="manual",
            errors=errors,
            data_schema=schema.Schema(
                {
                    schema.Optional(CONF_NAME, default=NAME): str,
                    schema.Required(CONF_HOST): str,
                    schema.Required(CONF_DEVICE_ID): str,
                    schema.Required(CONF_LOCAL_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )

    async def async_step_pi(self, user_input=None):
        errors = {}
        if user_input is not None:
            path = self.hass.config.path(CREDENTIAL_FILE)
            try:
                data = await self.hass.async_add_executor_job(load_pi_credentials, path)
            except OSError, ValueError, KeyError:
                errors["base"] = "pi_credentials_missing"
            else:
                result, errors = await self._async_finish(data, NAME)
                if result is not None:
                    # The returned entry contains the credentials; remove the temporary export.
                    try:
                        await self.hass.async_add_executor_job(Path(path).unlink, True)
                    except OSError:
                        pass
                    return result
        return self.async_show_form(step_id="pi", errors=errors, data_schema=schema.Schema({}))

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = dict(entry.data)
            data[CONF_HOST] = user_input[CONF_HOST]
            if user_input.get(CONF_LOCAL_KEY):
                data[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY]
            try:
                clean = await async_call(self.hass, validate_local, data)
            except ValueError:
                errors["base"] = "invalid_credentials"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=clean)
        return self.async_show_form(
            step_id="reconfigure",
            errors=errors,
            data_schema=schema.Schema(
                {
                    schema.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    schema.Optional(CONF_LOCAL_KEY, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MangoOptionsFlow()


class MangoOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=schema.Schema(
                {
                    schema.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): schema.All(
                        schema.Coerce(int), schema.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
                    ),
                }
            ),
        )
