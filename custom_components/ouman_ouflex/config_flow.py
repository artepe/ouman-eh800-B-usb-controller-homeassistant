"""Explicit map import; connection validation only uses reads."""
from __future__ import annotations
import json
import voluptuous as vol
from homeassistant import config_entries
from . import DOMAIN
from .modbus import Client
from .pointmap import load_map, map_digest


class OuflexFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OuflexOptions()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                doc, points = load_map(user_input['map_json'])
                if len(points) > 256:
                    raise ValueError('HA maps limited to 256 points per entry')
                client = Client(user_input['host'], user_input['port'], user_input['unit_id'])
                p = points[0]
                await self.hass.async_add_executor_job(client.read, p.offset, p.count, p.function)
                await self.async_set_unique_id('%s:%s:%s' % (user_input['host'], user_input['port'], user_input['unit_id']))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title='Ouman ' + doc['identity']['model'], data=user_input)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors['base'] = 'invalid_map'
            except Exception:
                errors['base'] = 'cannot_connect'
        return self.async_show_form(step_id='user', errors=errors, data_schema=vol.Schema({
            vol.Required('host'): str,
            vol.Required('port', default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required('unit_id', default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Required('map_json'): str,
        }))


class OuflexOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                policy = json.loads(user_input['write_policy'])
                doc, _ = load_map(self.config_entry.data['map_json'])
                if user_input['allow_writes'] and (policy.get('map_sha256') != map_digest(doc)
                    or policy.get('identity') != doc['identity']):
                    raise ValueError('Policy identity/digest mismatch')
                return self.async_create_entry(title='', data=user_input)
            except (ValueError, TypeError, AttributeError):
                errors['base'] = 'invalid_policy'
        return self.async_show_form(step_id='init', errors=errors, data_schema=vol.Schema({
            vol.Required('allow_writes', default=self.config_entry.options.get('allow_writes', False)): bool,
            vol.Required('write_policy', default=self.config_entry.options.get('write_policy', '{}')): str,
        }))
