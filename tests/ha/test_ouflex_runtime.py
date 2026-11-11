"""Full HA setup/config-flow/service tests with official pytest-homeassistant.

Run separately from contract tests, which use explicit framework doubles.
"""
from dataclasses import asdict
import json
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.ouman_ouflex.modbus import Client
from custom_components.ouman_ouflex.pointmap import Point, load_map, map_digest


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    return hass_tmp_config_dir


@pytest.fixture
def device():
    points = [
        Point('measurement','Synthetic measurement',1,1,'s16'),
        Point('target','Synthetic target',2,1,'u16',minimum=0,maximum=100,
              access='RW',entity='number',source='synthetic fixture'),
        Point('switch','Synthetic switch',3,1,'u16',minimum=0,maximum=1,
              access='RW',entity='switch',source='synthetic fixture'),
        Point('select','Synthetic select',4,1,'u16',minimum=0,maximum=1,
              access='RW',entity='select',enums={'0':'Off','1':'On'},source='synthetic fixture'),
        Point('alarm','Synthetic alarm',5,1,'u16',entity='alarm'),
    ]
    doc,_ = load_map(json.dumps(dict(schema_version=1,
        identity=dict(model='SIMULATOR',firmware='test',application='fixture'),
        points=[asdict(p) for p in points])))
    policy=dict(identity=doc['identity'],map_sha256=map_digest(doc),points={
        p.key:dict(documentation='synthetic fixture',reviewed_by='test',physically_verified=True)
        for p in points if p.access=='RW'})
    registers={0:23,1:7,2:0,3:0,4:39}
    calls=[]
    def read(self,address,count=1,function=3,**kwargs):
        calls.append(('read',address,count))
        return [registers[address+i] for i in range(count)]
    def write(self,address,words,function=16,**kwargs):
        calls.append(('write',address,words))
        registers.update({address+i:v for i,v in enumerate(words)})
        return b''
    with patch.object(Client,'read',read),patch.object(Client,'write',write):
        yield dict(data=dict(host='127.0.0.1',port=1502,unit_id=1,map_json=json.dumps(doc)),
                   policy=policy,calls=calls,registers=registers)


async def setup(hass,device,write=False):
    entry=MockConfigEntry(domain='ouman_ouflex',title='Synthetic Ouflex',
        data=device['data'],options=dict(allow_writes=write,write_policy=json.dumps(device['policy'])))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass,entry,platform,key):
    return er.async_get(hass).async_get_entity_id(platform,'ouman_ouflex',entry.entry_id+'_'+key)


async def test_read_only_setup_unload(hass,device):
    entry=await setup(hass,device)
    assert hass.states.get(entity_id(hass,entry,'sensor','measurement')).state=='23.0'
    assert hass.states.get(entity_id(hass,entry,'binary_sensor','alarm')).state=='on'
    assert entity_id(hass,entry,'number','target') is None
    assert hass.states.get(entity_id(hass,entry,'sensor','target')).state=='7.0'
    assert all(call[0]=='read' for call in device['calls'])
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_control_services_with_readback(hass,device):
    entry=await setup(hass,device,write=True)
    number=entity_id(hass,entry,'number','target')
    await hass.services.async_call('number','set_value',{'entity_id':number,'value':22},blocking=True)
    switch=entity_id(hass,entry,'switch','switch')
    await hass.services.async_call('switch','turn_on',{'entity_id':switch},blocking=True)
    select=entity_id(hass,entry,'select','select')
    await hass.services.async_call('select','select_option',{'entity_id':select,'option':'On'},blocking=True)
    await hass.async_block_till_done()
    assert device['registers'][1]==22
    assert device['registers'][2]==1
    assert device['registers'][3]==1
    assert hass.states.get(number).state=='22.0'
    assert hass.states.get(switch).state=='on'
    assert hass.states.get(select).state=='On'


async def test_flow_invalid_map_and_read_only_success(hass,device):
    result=await hass.config_entries.flow.async_init('ouman_ouflex',context={'source':config_entries.SOURCE_USER})
    assert result['type']==FlowResultType.FORM
    bad={**device['data'],'map_json':'{}'}
    result=await hass.config_entries.flow.async_configure(result['flow_id'],bad)
    assert result['errors']['base']=='invalid_map'
    result=await hass.config_entries.flow.async_configure(result['flow_id'],device['data'])
    assert result['type']==FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert all(call[0]=='read' for call in device['calls'])


async def test_total_read_failure_marks_entry_retry(hass,device):
    device['registers'].clear()
    entry=MockConfigEntry(domain='ouman_ouflex',data=device['data'])
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_register_browser_selects_points_and_preserves_write_policy(hass, device):
    entry = await setup(hass, device)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result['type'] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result['flow_id'], {'next_step_id': 'register_browser'})
    result = await hass.config_entries.options.async_configure(
        result['flow_id'], {'selected_points': ['measurement', 'alarm']})
    assert result['type'] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert {p.key for p in entry.runtime_data.points} == {'measurement', 'alarm'}
    assert json.loads(entry.options['write_policy']) == device['policy']
    assert not any(call[0] == 'write' for call in device['calls'])


async def test_map_reimport_disables_writes_and_reloads(hass, device):
    entry = await setup(hass, device, write=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result['flow_id'], {'next_step_id': 'register_map'})
    result = await hass.config_entries.options.async_configure(
        result['flow_id'], {'map_json': '<broken', 'firmware': 'test'})
    assert result['errors'] == {'base': 'invalid_map'}
    result = await hass.config_entries.options.async_configure(
        result['flow_id'], {'map_json': device['data']['map_json'], 'firmware': 'test'})
    assert result['type'] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options['allow_writes'] is False
    assert entry.options['write_policy'] == '{}'
    assert not any(entry.runtime_data.can_write(p) for p in entry.runtime_data.points)
    assert not any(call[0] == 'write' for call in device['calls'])
