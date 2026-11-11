"""Real Home Assistant flow/runtime tests; run separately from portable tests."""
from unittest.mock import AsyncMock, patch
import json

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant.common import MockConfigEntry

from custom_components.openlvi.modbus_research import DiscoveryDriver
from custom_components.openlvi.profiles import parse_profile

DATA = dict(vendor='Ouman', model='Ouflex', transport='modbus_tcp',
            host='192.168.10.105', port=502, unit_id=1, discovery_mode=True)
MAP = json.dumps({'registers': [{'key': 'verified', 'name': 'Verified reading',
                                'address': 201, 'kind': 's16', 'decimals': 1}]})


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


async def connection_step(hass):
    result = await hass.config_entries.flow.async_init('openlvi', context={'source': 'user'})
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'vendor': 'Ouman'})
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'model': 'Ouflex'})
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'transport': 'modbus_tcp'})
    assert result['step_id'] == 'connection'
    return result


@pytest.mark.parametrize('diag', [
    {'tcp_connected': True, 'modbus_response': True, 'success': False,
     'exception_code': 1, 'exception_name': 'Illegal Function'},
    {'tcp_connected': True, 'modbus_response': False, 'success': False, 'error': 'TimeoutError'},
])
async def test_add_discovery_without_map_or_firmware(hass, diag):
    with patch('custom_components.openlvi.config_flow.probe', AsyncMock(return_value=diag)), \
         patch('custom_components.openlvi.config_flow.make_transport') as make, \
         patch('custom_components.openlvi.async_setup_entry', AsyncMock(return_value=True)):
        result = await connection_step(hass)
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {
            'host': DATA['host'], 'port': 502, 'unit_id': 1, 'discovery_mode': True})
        assert result['step_id'] == 'discovery_result'
        assert 'tcp_connected' in result['description_placeholders']['diagnostics']
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {})
        assert result['type'] is FlowResultType.CREATE_ENTRY
        assert result['data']['discovery_mode'] is True
        assert result['data']['allow_writes'] is False
        assert result['data']['profile_json'] == ''
        make.assert_not_called()  # No ordinary register reads in discovery.


async def test_tcp_failure_is_not_a_missing_map_error(hass):
    with patch('custom_components.openlvi.config_flow.probe', AsyncMock(return_value={
            'tcp_connected': False, 'error': 'Connection refused'})):
        result = await connection_step(hass)
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {
            'host': DATA['host'], 'port': 502, 'unit_id': 1, 'discovery_mode': True})
        assert result['errors'] == {'base': 'cannot_connect_tcp'}


class MappedDriver:
    def __init__(self, data):
        self.data = data
        self.points = parse_profile(data['profile_json'])
        self.async_connect = AsyncMock()
        self.async_read = AsyncMock(return_value={'verified': 21.5})
        self.async_close = AsyncMock()
        self.async_write = AsyncMock(side_effect=AssertionError('Unexpected write'))


async def test_normal_mode_reads_confirmed_map(hass):
    drivers = []
    def make(hass, data):
        driver = MappedDriver(data)
        drivers.append(driver)
        return driver
    with patch('custom_components.openlvi.config_flow.make_transport', side_effect=make), \
         patch('custom_components.openlvi.async_setup_entry', AsyncMock(return_value=True)):
        result = await connection_step(hass)
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {
            'host': DATA['host'], 'port': 502, 'unit_id': 1, 'discovery_mode': False,
            'profile_json': MAP, 'profile_confirmed': True})
        assert result['type'] is FlowResultType.CREATE_ENTRY
        drivers[0].async_read.assert_awaited_once()
        drivers[0].async_close.assert_awaited_once()
        drivers[0].async_write.assert_not_called()


async def test_normal_mode_missing_map_and_unconfirmed_map_rejected(hass):
    result = await connection_step(hass)
    for extra in ({}, {'profile_json': MAP}):
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {
            'host': DATA['host'], 'port': 502, 'unit_id': 1, 'discovery_mode': False, **extra})
        assert result['errors'] == {'base': 'invalid_profile'}


async def setup_discovery(hass):
    entry = MockConfigEntry(domain='openlvi', data=DATA, title='Ouman Ouflex')
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_discovery_creates_device_and_only_connection_entity(hass):
    with patch('custom_components.openlvi.modbus_research.tcp_status',
               AsyncMock(return_value={'tcp_connected': True})):
        entry = await setup_discovery(hass)
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len(entities) == 1
        state = hass.states.get(entities[0].entity_id)
        assert state.state == 'tcp_connected'
        assert state.attributes['register_entities'] == 0
        assert any(('openlvi', entry.entry_id) in device.identifiers for device in
                   dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id))
        with patch('custom_components.openlvi.modbus_research.tcp_status',
                   AsyncMock(return_value={'tcp_connected': False})):
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get(entities[0].entity_id).state == 'tcp_disconnected'
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_discovery_can_load_after_restart(hass):
    with patch('custom_components.openlvi.modbus_research.tcp_status',
               AsyncMock(return_value={'tcp_connected': False})):
        entry = await setup_discovery(hass)
        assert isinstance(entry.runtime_data.driver, DiscoveryDriver)
        assert entry.runtime_data.driver.points == []


async def test_import_map_later_reload_creates_confirmed_sensor(hass):
    with patch('custom_components.openlvi.modbus_research.tcp_status',
               AsyncMock(return_value={'tcp_connected': True})):
        entry = await setup_discovery(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result['type'] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result['flow_id'], {'next_step_id': 'register_map'})
    with patch('custom_components.openlvi.make_transport', side_effect=lambda hass, data: MappedDriver(data)):
        result = await hass.config_entries.options.async_configure(result['flow_id'], {
            'discovery_mode': False, 'profile_json': MAP, 'profile_confirmed': True, 'unit_id': 2})
        assert result['type'] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert entry.runtime_data.driver.data['unit_id'] == 2
    assert entry.runtime_data.driver.points[0].key == 'verified'
    entity = er.async_get(hass).async_get_entity_id('sensor', 'openlvi', entry.entry_id + '_verified_sensor')
    assert hass.states.get(entity).state == '21.5'
    entry.runtime_data.driver.async_write.assert_not_called()


async def test_options_research_returns_exceptions_without_creating_entities(hass):
    with patch('custom_components.openlvi.modbus_research.tcp_status',
               AsyncMock(return_value={'tcp_connected': True})):
        entry = await setup_discovery(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result['flow_id'], {'next_step_id': 'research'})
    diag = {'tcp_connected': True, 'modbus_response': True, 'exception_code': 2,
            'exception_name': 'Illegal Data Address', 'success': False}
    with patch('custom_components.openlvi.modbus_research.probe', AsyncMock(return_value=diag)) as probe:
        result = await hass.config_entries.options.async_configure(result['flow_id'], {
            'unit_ids': '1,2', 'function': 3, 'address': 201, 'address_base': 1,
            'count': 1, 'documented': True})
        assert result['step_id'] == 'research_result'
        assert 'Illegal Data Address' in result['description_placeholders']['diagnostics']
        assert [call.args[2] for call in probe.await_args_list] == [1, 2]
    assert entry.runtime_data.driver.points == []
    assert len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 1


async def test_action_read_only_response_and_invalid_writes(hass):
    with patch('custom_components.openlvi.modbus_research.tcp_status',
               AsyncMock(return_value={'tcp_connected': True})):
        entry = await setup_discovery(hass)
    with patch('custom_components.openlvi.modbus_research.probe', AsyncMock(return_value={
            'tcp_connected': True, 'modbus_response': True, 'registers': [215]})) as probe:
        response = await hass.services.async_call('openlvi', 'research_registers', {
            'config_entry_id': entry.entry_id, 'unit_ids': '2', 'function': '3',
            'address': 201, 'address_base': 1, 'count': 1, 'documented': True},
            blocking=True, return_response=True)
        assert response['results'][0]['registers'] == [215]
        assert response['controller_settings_changed'] is False
        probe.assert_awaited_once()
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call('openlvi', 'research_registers', {
                'config_entry_id': entry.entry_id, 'unit_ids': '2', 'function': 3,
                'address': 201}, blocking=True, return_response=True)
        assert probe.await_count == 1
