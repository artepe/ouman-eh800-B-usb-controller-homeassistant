"""HA adapter contract tests with explicit minimal framework doubles.

These tests do not claim a complete Home Assistant runtime installation test.
"""
from __future__ import annotations
import asyncio
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_ouflex_lab import fixture, WireSocket, sim


class FrameworkEntity:
    def __init__(self,coordinator=None):
        self.coordinator=coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success


class FrameworkCoordinator:
    def __init__(self,hass,*args,**kwargs):
        self.hass=hass
        self.data={}
        self.last_update_success=True

    async def async_request_refresh(self):
        self.data=await self._async_update_data()


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules={}
        def module(name,**attrs):
            m=types.ModuleType(name);m.__dict__.update(attrs);modules[name]=m
        module('homeassistant')
        module('homeassistant.helpers')
        module('homeassistant.helpers.update_coordinator', CoordinatorEntity=FrameworkEntity,
               DataUpdateCoordinator=FrameworkCoordinator,UpdateFailed=RuntimeError)
        module('homeassistant.helpers.entity',EntityCategory=types.SimpleNamespace(DIAGNOSTIC='diagnostic'))
        module('homeassistant.exceptions',HomeAssistantError=RuntimeError)
        module('homeassistant.components')
        for kind,classname in [('sensor','SensorEntity'),('binary_sensor','BinarySensorEntity'),
                               ('number','NumberEntity'),('select','SelectEntity'),('switch','SwitchEntity')]:
            attrs={classname:type(classname,(),{})}
            if kind=='number':attrs['NumberMode']=types.SimpleNamespace(BOX='box')
            if kind=='binary_sensor':attrs['BinarySensorDeviceClass']=types.SimpleNamespace(CONNECTIVITY='connectivity')
            module('homeassistant.components.'+kind,**attrs)
        cls.patch=patch.dict(sys.modules,modules)
        cls.patch.start()
        cls.coordinator_module=importlib.import_module('custom_components.ouman_ouflex.coordinator')
        cls.entities={k:importlib.import_module('custom_components.ouman_ouflex.'+k)
                      for k in ('sensor','binary_sensor','number','select','switch','diagnostics')}

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.doc,self.points,self.policy=fixture()
        self.entry=types.SimpleNamespace(entry_id='test',data=dict(map_json=json.dumps(self.doc),
            host='synthetic',port=502,unit_id=1),options={},runtime_data=None)
        async def executor(function,*args):return function(*args)
        self.hass=types.SimpleNamespace(async_add_executor_job=executor,
            config=types.SimpleNamespace(path=lambda *p:str(Path(self.temp.name).joinpath(*p))))
        self.model=sim.Model()
        self.model.holding[0]=0
        self.socket_patch=patch('socket.create_connection',side_effect=lambda *a,**k:WireSocket(self.model))
        self.socket_patch.start();self.addCleanup(self.socket_patch.stop)

    def coordinator(self,enabled=False):
        self.entry.options=dict(allow_writes=enabled,write_policy=json.dumps(self.policy))
        async def construct():
            return self.coordinator_module.OuflexCoordinator(self.hass,self.entry)
        c=asyncio.run(construct())
        self.entry.runtime_data=c
        return c

    def test_read_only_by_default_and_entity_fallback(self):
        c=self.coordinator()
        c.data=asyncio.run(c._async_update_data())
        self.assertEqual(c.data['target'],-12.3)
        self.assertFalse(c.can_write(self.points[0]))
        added=[]
        asyncio.run(self.entities['sensor'].async_setup_entry(self.hass,self.entry,added.extend))
        self.assertEqual(len(added),2)
        self.assertTrue(added[0].available)
        self.assertTrue(all(p[0] in (3,4) for p in self.model.requests))

    def test_number_switch_write_readback(self):
        c=self.coordinator(True)
        number=self.entities['number'].OuflexNumber(c,self.points[1])
        self.assertEqual(number.native_step,.1)
        asyncio.run(number.async_set_native_value(-21.2))
        self.assertEqual(number.native_value,-21.2)
        switch=self.entities['switch'].OuflexSwitch(c,self.points[0])
        asyncio.run(switch.async_turn_on())
        self.assertTrue(switch.is_on)
        self.assertTrue(Path(self.temp.name,'.storage','ouflex_test.jsonl').exists())

    def test_write_policy_requires_actual_bool_physical_verification(self):
        for value in (False,'true',None):
            self.policy['points']['flag']['physically_verified']=value
            c=self.coordinator(True)
            self.assertFalse(c.can_write(self.points[0]))

    def test_partial_and_total_failure(self):
        c=self.coordinator()
        self.model.holding.pop(0)
        c.data=asyncio.run(c._async_update_data())
        self.assertIn('flag',c.point_errors)
        self.assertNotIn('flag',c.data)
        entity=self.entities['sensor'].OuflexSensor(c,self.points[0])
        self.assertFalse(entity.available)
        self.model.reject_reads=True
        with self.assertRaises(RuntimeError):asyncio.run(c._async_update_data())

    def test_select_and_alarm_semantics(self):
        c=self.coordinator(True)
        c.data={'flag':1}
        selectpoint=replace(self.points[0],entity='select',enums={'0':'Off','1':'On'})
        entity=self.entities['select'].OuflexSelect(c,selectpoint)
        self.assertEqual(entity.current_option,'On')
        self.assertEqual(entity.options,['Off','On'])
        with self.assertRaises(ValueError):asyncio.run(entity.async_select_option('invalid'))
        alarm=replace(self.points[0],entity='alarm')
        c.data={'flag':39}
        entity=self.entities['binary_sensor'].OuflexBinary(c,alarm)
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.extra_state_attributes['priority'],1)

    def test_diagnostics_redact_endpoint_and_names(self):
        c=self.coordinator()
        c.data=asyncio.run(c._async_update_data())
        result=asyncio.run(self.entities['diagnostics'].async_get_config_entry_diagnostics(self.hass,self.entry))
        text=json.dumps(result)
        self.assertNotIn('synthetic',text)
        self.assertNotIn('Synthetic U16',text)
        self.assertNotIn('map_json',text)


if __name__=='__main__':unittest.main()
