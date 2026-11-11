"""Explicit map import; connection validation only uses reads."""
from __future__ import annotations
import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from . import DOMAIN
from .modbus import Client
from .pointmap import load_map, map_digest
from .ftp_map import fetch_application_map


class OuflexFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OuflexOptions()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                if user_input.get('auto_ftp_map', True):
                    doc = await self.hass.async_add_executor_job(
                        fetch_application_map, user_input['host'])
                    data = {**user_input, 'map_json': json.dumps(doc, ensure_ascii=False)}
                else:
                    doc, _ = load_map(user_input.get('map_json', ''))
                    data = user_input
                _, points = load_map(json.dumps(doc))
                if len(points) > 256:
                    raise ValueError('HA maps limited to 256 points per entry')
                client = Client(data['host'], data['port'], data['unit_id'])
                first = points[0]
                await self.hass.async_add_executor_job(
                    client.read, first.offset, first.count, first.function)
                await self.async_set_unique_id(
                    '%s:%s:%s' % (data['host'], data['port'], data['unit_id']))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title='Open HVAC · ' + doc['identity']['model'], data=data)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors['base'] = 'invalid_map'
            except Exception:
                errors['base'] = 'cannot_connect'
        return self.async_show_form(step_id='user', errors=errors, data_schema=vol.Schema({
            vol.Required('host', default='192.168.10.105'): str,
            vol.Required('port', default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required('unit_id', default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Required('auto_ftp_map', default=True): bool,
            vol.Optional('map_json', default=''): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)),
        }))


class OuflexOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id='init', menu_options=['register_browser', 'register_map', 'write_access'])

    async def async_step_register_browser(self, user_input=None):
        doc, points = load_map(self.config_entry.options.get('map_json', self.config_entry.data['map_json']))
        errors = {}
        if user_input is not None:
            selected = user_input.get('selected_points', [])
            if not selected or not set(selected) <= {p.key for p in points}:
                errors['base'] = 'invalid_map'
            else:
                return self.async_create_entry(title='', data={**self.config_entry.options, **user_input})
        choices = [{'value': p.key, 'label': '%s | %s [%s] %s' %
                    (p.name, p.address, p.address_base, p.kind)} for p in points]
        return self.async_show_form(step_id='register_browser', errors=errors, data_schema=vol.Schema({
            vol.Required('selected_points', default=self.config_entry.options.get(
                'selected_points', [p.key for p in points])): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices, multiple=True)),
        }))

    async def async_step_register_map(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                text = user_input['map_json']
                if text.lstrip('\ufeff \r\n').startswith('<'):
                    from .ounet import import_ounet
                    doc = import_ounet(text, firmware=user_input['firmware'])
                else:
                    doc, _ = load_map(text)
                _, points = load_map(json.dumps(doc))
                if len(points) > 256:
                    raise ValueError('At most 256 points')
                updated = {**self.config_entry.options, 'map_json': json.dumps(doc),
                           'selected_points': [p.key for p in points],
                           'allow_writes': False, 'write_policy': '{}'}
                return self.async_create_entry(title='', data=updated)
            except (ValueError, TypeError, KeyError):
                errors['base'] = 'invalid_map'
        return self.async_show_form(step_id='register_map', errors=errors, data_schema=vol.Schema({
            vol.Required('map_json'): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Required('firmware', default='unknown'): str,
        }))

    async def async_step_write_access(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                policy = json.loads(user_input['write_policy'])
                doc, _ = load_map(self.config_entry.options.get('map_json', self.config_entry.data['map_json']))
                if user_input['allow_writes'] and (policy.get('map_sha256') != map_digest(doc)
                    or policy.get('identity') != doc['identity']):
                    raise ValueError('Policy identity/digest mismatch')
                return self.async_create_entry(title='', data={**self.config_entry.options, **user_input})
            except (ValueError, TypeError, AttributeError):
                errors['base'] = 'invalid_policy'
        return self.async_show_form(step_id='write_access', errors=errors, data_schema=vol.Schema({
            vol.Required('allow_writes', default=self.config_entry.options.get('allow_writes', False)): bool,
            vol.Required('write_policy', default=self.config_entry.options.get('write_policy', '{}')): str,
        }))
