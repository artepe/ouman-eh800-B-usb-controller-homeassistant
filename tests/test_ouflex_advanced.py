"""Synthetic fixtures only. Never publish captured site configurations here."""
import json
from pathlib import Path
import threading
import struct
import unittest
from unittest.mock import patch

from test_ouflex_lab import WireSocket, sim, fixture
from custom_components.ouman_ouflex.modbus import Client, ModbusError
from custom_components.ouman_ouflex.ounet import import_ounet
from custom_components.ouman_ouflex.pointmap import load_map, alarm_state
from custom_components.ouman_ouflex.session import Session

XML = '''<controllertemplate name="SYNTHETIC" version="test" type="Modbus">
<targetdetails address="PRIVATE MUST NOT EXPORT" loader="PRIVATE USER"/>
<groups><group name="Fixture"><point name="Temperature" pointid="fake.temp" pointtype="6"
registertype="Holding" addressformat="S32" addressindex="201" decimals="1" scaling="10"
min="-50" max="130" unit="°C" writeacceslevel="3">
<point name="Mode" pointid="fake.mode" pointtype="5" registertype="Holding" addressformat="U16"
addressindex="305" enum="0=Auto;1=Manual"/></point>
<point name="Digital" pointid="fake.input" pointtype="8" registertype="Holding"
addressformat="S32" addressindex="221" enum="0=Off;1=On"/>
<point name="Alarm" pointid="fake.alarm" pointtype="14" addressindex="492" mask="1"
addressackmask="2" addressprioritymask="28" addressgroupmask="480" ackindex="60"
transferackindex="87" ackvalue="0"/>
<point name="Calendar" pointid="fake.calendar" pointtype="15" addressindex="10003" addressmultiple="120"/>
</group></groups></controllertemplate>'''


class ImportTests(unittest.TestCase):
    def test_observed_schema_preserves_types_and_no_site_data_or_write_authority(self):
        doc = import_ounet(XML, firmware='synthetic')
        _, points = load_map(json.dumps(doc))
        self.assertEqual(len(points), 4)
        self.assertEqual(points[0].offset, 200)
        self.assertEqual(points[0].manual_reg, 305)
        self.assertEqual(points[0].decimals, 1)
        self.assertEqual(points[2].entity, 'binary_sensor')
        self.assertEqual(points[2].count, 2)
        self.assertTrue(all(p.access == 'R' for p in points))
        self.assertNotIn('PRIVATE', json.dumps(doc))
        self.assertEqual(doc['structured_read_ranges'][0]['count'], 120)
        self.assertEqual(doc['rejected_rows'], [])
        with self.assertRaises(ValueError):
            Session(Client('unused'), doc, points, enabled=True).permitted(points[0].key)

    def test_unknown_schema_scaling_and_datatypes_fail_closed(self):
        with self.assertRaises(ValueError):
            import_ounet(XML.replace('controllertemplate', 'unknown'), firmware='test')
        with self.assertRaises(ValueError):
            import_ounet('<!DOCTYPE x>'+XML, firmware='test')
        doc = import_ounet(XML.replace('scaling="10"', 'scaling="100"'), firmware='test')
        self.assertEqual(len(doc['rejected_rows']), 1)
        doc = import_ounet(XML.replace('addressformat="S32"', 'addressformat="STRING"'), firmware='test')
        self.assertEqual(len(doc['rejected_rows']), 2)

    def test_device_specific_alarm_group_mask_overrides_generic_default(self):
        masks = {'active': 1, 'unacknowledged': 2, 'priority': 28, 'group': 480}
        state = alarm_state(1 | 2 | (3 << 2) | (10 << 5), masks)
        self.assertEqual(state['group'], 10)
        self.assertEqual(state['priority'], 3)
        self.assertTrue(state['active'])


class BitProtocolTests(unittest.TestCase):
    def setUp(self):
        self.model = sim.Model()
        self.client = Client('synthetic')
        self.patch = patch('socket.create_connection', side_effect=lambda *a, **k: WireSocket(self.model))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_single_and_multiple_coils_readback_restore(self):
        original = self.client.read_bits(0, 9)
        self.client.write_bits(0, [True], 5)
        self.assertEqual(self.client.read_bits(0), [True])
        desired = [True, False, True, True, False, False, True, False, True]
        self.client.write_bits(0, desired, 15)
        self.assertEqual(self.client.read_bits(0, 9), desired)
        self.client.write_bits(0, original, 15)
        self.assertEqual(self.client.read_bits(0, 9), original)
        self.assertEqual(self.client.read_bits(0, 1, 2), [True])
        self.assertTrue(all(e['response_hex'] and e['duration_ms'] >= 0 for e in self.client.events))

    def test_unknown_coils_and_invalid_values(self):
        with self.assertRaises(ModbusError) as ctx:
            self.client.write_bits(999, [True], 5)
        self.assertEqual(ctx.exception.exception_code, 2)
        count = len(self.model.requests)
        for bits, fc in (([1], 5), ([], 15), ([True, False], 5), ([True]*1969, 15)):
            with self.assertRaises(ValueError):
                self.client.write_bits(0, bits, fc)
        self.assertEqual(len(self.model.requests), count)
        self.assertEqual(self.model.reply(bytes.fromhex('0500000001')), bytes([133, 3]))
        self.assertEqual(self.model.reply(bytes.fromhex('0f000000090101')), bytes([143, 3]))

    def test_bad_bit_byte_count_and_padding_rejected(self):
        for pdu in (b'\x01\x02\x01', b'\x01\x01\x80'):
            with patch.object(self.model, 'reply', return_value=pdu), self.assertRaises(ModbusError):
                self.client.read_bits(0)

    def test_nc_uses_same_binary_framing_and_does_not_corrupt_ff_bytes(self):
        with patch('custom_components.ouman_ouflex.nc_transport.NetcatSocket',
                   side_effect=lambda *args: WireSocket(self.model)):
            nc = Client('127.0.0.1', transport='nc')
            self.assertEqual(nc.read(1), [65535])
            self.assertTrue(nc.events[-1]['tcp_connected'])
            self.assertEqual(nc.events[-1]['transport'], 'nc')

    def test_display_observer_failure_still_restores_original(self):
        doc, points, policy = fixture()
        self.model.holding[0] = 0
        self.client.audit = lambda event: None
        session = Session(self.client, doc, points, policy, enabled=True)
        def observe(result):
            self.assertEqual(self.model.holding[0], 1)
            raise RuntimeError('observer disconnected')
        result = session.write_test('flag', 1, disconnected=True, observer=observe)
        self.assertTrue(result['restored'])
        self.assertFalse(result['success'])
        self.assertEqual(self.model.holding[0], 0)


class NetcatLoopbackTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/bin/nc').exists(), 'netcat not installed')
    def test_actual_subprocess_binary_roundtrip(self):
        server = sim.Server(('127.0.0.1', 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client('127.0.0.1', server.server_address[1], transport='nc')
            self.assertEqual(client.read(1), [65535])
            client.write_bits(0, [True]*9)
            self.assertEqual(client.read_bits(0, 9), [True]*9)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class FTPBoundaryTests(unittest.TestCase):
    def test_path_and_host_validation_before_subprocess(self):
        from tools.ouflex_ftp import fetch
        with patch('tools.ouflex_ftp.subprocess.run') as run:
            for host, path in [('example.com', '/files/'), ('192.168.1.1', '/../commands'),
                               ('192.168.1.1', '/files/\r\nDELE x')]:
                with self.assertRaises(ValueError):
                    fetch(host, path)
            run.assert_not_called()

    def test_command_directories_are_listed_but_never_retrieved(self):
        import tempfile
        from tools.ouflex_ftp import collect
        calls = []
        def fetch(host, path, **kwargs):
            calls.append((path, kwargs.get('listing', False)))
            if path in ('/commands/', '/updates/', '/new_application/'):
                return b'unknown-action\n'
            return b''
        with tempfile.TemporaryDirectory() as directory, patch('tools.ouflex_ftp.fetch', fetch):
            result = collect('192.168.1.1', Path(directory)/'new')
        self.assertEqual(result['errors'], [])
        self.assertFalse(any('unknown-action' in path for path, listing in calls))


if __name__ == '__main__':
    unittest.main()
