"""Portable protocol tests. Synthetic bytes, never evidence about real Ouflex."""
from __future__ import annotations
import asyncio
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

BASE = Path(__file__).resolve().parents[1] / 'custom_components/openlvi'
PACKAGE = '_openlvi_discovery_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package


def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE + '.' + name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


research = load('modbus_research')
profiles = load('profiles')


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def wire(self, reply_pdu, **kwargs):
        reader = asyncio.StreamReader()
        sent = []
        class Writer:
            def write(self, packet):
                sent.append(packet)
                unit = packet[6]
                reader.feed_data(struct.pack('>HHHB', 1, 0, len(reply_pdu)+1, unit) + reply_pdu)
                reader.feed_eof()
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass
        with patch.object(research.asyncio, 'open_connection', AsyncMock(return_value=(reader, Writer()))):
            result = await research.probe('test', 502, kwargs.pop('unit', 1), **kwargs)
        return result, sent

    async def test_identify_exception_keeps_tcp_and_modbus_success_separate(self):
        result, sent = await self.wire(b'\xab\x01')
        self.assertTrue(result['tcp_connected'])
        self.assertTrue(result['modbus_response'])
        self.assertFalse(result['success'])
        self.assertEqual(result['exception_name'], 'Illegal Function')
        self.assertEqual(sent[0][7:], b'\x2b\x0e\x01\x00')

    async def test_fc03_address_conversion_and_raw_words(self):
        result, sent = await self.wire(b'\x03\x04\xff\xff\x00\x0a', function=3,
                                       address=201, address_base=1, count=2, unit=255)
        self.assertEqual(sent[0][6], 255)
        self.assertEqual(sent[0][7:], struct.pack('>BHH', 3, 200, 2))
        self.assertEqual(result['registers'], [65535, 10])
        self.assertTrue(result['success'])

    async def test_fc04_exception(self):
        result, sent = await self.wire(b'\x84\x02', function=4, address=0, count=1)
        self.assertEqual(result['exception_code'], 2)
        self.assertEqual(result['exception_name'], 'Illegal Data Address')
        self.assertEqual(sent[0][7], 4)

    async def test_identification_continuation_is_reported(self):
        result, _ = await self.wire(b'\x2b\x0e\x01\x01\xff\x03\x01\x00\x03ABC')
        self.assertEqual(result['objects'], {'0': 'ABC'})
        self.assertEqual(result['next_object'], 3)
        self.assertEqual(result['more_follows'], 255)

    async def test_bad_byte_count_not_success(self):
        result, _ = await self.wire(b'\x03\x01\x00', function=3, address=0)
        self.assertFalse(result['success'])
        self.assertIn('byte count', result['error'])

    async def test_tcp_failure_has_no_modbus_response(self):
        with patch.object(research.asyncio, 'open_connection', AsyncMock(side_effect=OSError('blocked'))):
            result = await research.probe('test', 502, 1)
        self.assertFalse(result['tcp_connected'])
        self.assertFalse(result['modbus_response'])
        self.assertEqual(result['error'], 'blocked')

    async def test_timeout_after_tcp_is_reported_without_register_fallback(self):
        class Writer:
            def write(self, packet): self.packet = packet
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass
        writer = Writer()
        reader = asyncio.StreamReader()
        with patch.object(research.asyncio, 'open_connection', AsyncMock(return_value=(reader, writer))):
            result = await research.probe('test', 502, 1, timeout=0.01)
        self.assertTrue(result['tcp_connected'])
        self.assertFalse(result['modbus_response'])
        self.assertEqual(writer.packet[7], 43)

    async def test_write_functions_and_broadcast_rejected_before_network(self):
        with patch.object(research.asyncio, 'open_connection', AsyncMock()) as connect:
            for function in (5, 6, 15, 16, 23):
                with self.assertRaises(ValueError):
                    await research.probe('test', 502, 1, function=function, address=0)
            with self.assertRaises(ValueError):
                await research.probe('test', 502, 0)
            connect.assert_not_awaited()

    async def test_discovery_offline_stays_loaded_with_zero_points(self):
        driver = research.DiscoveryDriver({'host': 'test', 'port': 502, 'allow_writes': True})
        with patch.object(research, 'tcp_status', AsyncMock(return_value={'tcp_connected': False})):
            self.assertEqual(await driver.async_read(), {'discovery_tcp_connected': False})
        self.assertEqual(driver.points, [])
        self.assertFalse(driver.data['allow_writes'])
        with self.assertRaises(ValueError):
            await driver.async_write(None, 1)

    async def test_explicit_unit_research_does_not_modify_entry_unit(self):
        driver = research.DiscoveryDriver({'host': 'test', 'port': 502,
                                           'transport': 'modbus_tcp', 'unit_id': 1})
        with patch.object(research, 'probe', AsyncMock(return_value={'success': True})) as probe:
            result = await research.research(driver, '1,2,255')
        self.assertEqual([c.args[2] for c in probe.await_args_list], [1, 2, 255])
        self.assertEqual(driver.data['unit_id'], 1)
        self.assertEqual(driver.last_research, result)
        self.assertEqual(driver.points, [])


class Boundaries(unittest.TestCase):
    def test_explicit_unit_bounds(self):
        for raw in ('0', '256', '1,1', '1-8', '', ',1', '1,2,3,4,5,6,7,8,9'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                research.unit_ids(raw)

    def test_no_profile_or_firmware_needed_in_discovery(self):
        self.assertEqual(profiles.profile_for('Ouflex', '', '', discovery_mode=True), [])
        with self.assertRaises(ValueError):
            profiles.profile_for('Ouflex', '', '')

    def test_normal_custom_and_builtin_profiles_preserved(self):
        points = profiles.profile_for('Ouflex', '', json.dumps({'registers': [
            {'key': 'verified', 'name': 'Verified', 'address': 5, 'writable': True}]}))
        self.assertEqual(points[0].address, 5)
        self.assertFalse(points[0].writable)
        self.assertTrue(profiles.profile_for('A203', '2.0.2', ''))

    def test_highest_register_and_count(self):
        self.assertEqual(research.read_parameters(65536, 1, 1, 3), 65535)
        with self.assertRaises(ValueError):
            research.read_parameters(65536, 1, 2, 3)
        with self.assertRaises(ValueError):
            research.read_parameters(0, 0, 33, 3)
        with self.assertRaises(ValueError):
            profiles.parse_profile('{"registers":[{"key":"x","name":"X","address":65536,"kind":"u32"}]}')


if __name__ == '__main__':
    unittest.main()
