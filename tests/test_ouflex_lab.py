"""Deterministic PDU tests plus an actual loopback TCP suite when allowed."""
from __future__ import annotations
import contextlib
from dataclasses import asdict, replace
import importlib.util
import json
import os
import tempfile
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from custom_components.ouman_ouflex.modbus import Client, ModbusError, address_offset
from custom_components.ouman_ouflex.pointmap import (Point, decode, encode, load_map,
    import_rows, map_digest, alarm_state)
from custom_components.ouman_ouflex.session import Session

spec = importlib.util.spec_from_file_location('ouflex_simulator', ROOT/'tools/ouflex_simulator.py')
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


def fixture():
    points = [Point('flag', 'Synthetic U16', 1, 1, 'u16', minimum=0, maximum=1,
                    access='RW', source='synthetic test fixture', entity='switch'),
              Point('target', 'Synthetic S32', 2, 1, 's32', decimals=1,
                    minimum=-100, maximum=100, access='RW', source='synthetic test fixture', entity='number')]
    doc, points = load_map(json.dumps(dict(schema_version=1,
        identity=dict(model='SIMULATOR', firmware='test', application='fixture'),
        points=[asdict(p) for p in points])))
    policy = dict(map_sha256=map_digest(doc), identity=doc['identity'],
                  points={p.key: dict(documentation='synthetic', reviewed_by='test', physically_verified=True)
                          for p in points})
    return doc, points, policy


class WireSocket:
    """Socket double only: model emits actual encoded MBAP/PDU bytes."""
    def __init__(self, model, mutate=None):
        self.model, self.mutate = model, mutate
        self.buffer = b''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def settimeout(self, value):
        pass

    def sendall(self, request):
        tid, proto, length, unit = struct.unpack('>HHHB', request[:7])
        if len(request) != length+6:
            raise AssertionError('Invalid outgoing MBAP length')
        reply = self.model.reply(request[7:])
        if request[7] in (6,16) and self.model.drop_after_write and not self.model.dropped:
            self.model.dropped = True
            self.buffer = b''
            return
        self.buffer = struct.pack('>HHHB', tid, proto, len(reply)+1, unit) + reply
        if self.mutate:
            self.buffer = self.mutate(self.buffer)

    def recv(self, n):
        result, self.buffer = self.buffer[:min(n, 2)], self.buffer[min(n, 2):]
        return result


class CodecTests(unittest.TestCase):
    def test_signed_unsigned_boundaries_all_orders(self):
        for kind, values in [('u16', [0,65535]), ('s16',[-32768,32767]),
                             ('u32',[0,4294967295]), ('s32',[-2147483648,2147483647])]:
            for byte in ('big','little'):
                for word in ('big','little'):
                    p = Point('x','x',1,1,kind,minimum=min(values), maximum=max(values), byte_order=byte,word_order=word)
                    for value in values:
                        self.assertEqual(decode(encode(value,p),p),value)

    def test_s32_negative_ouman_order(self):
        p = fixture()[1][1]
        self.assertEqual(encode(-12.3,p),[65535,65413])
        self.assertEqual(decode([65535,65413],p),-12.3)
        for v in (-100.1, 'nan', 'inf', 0.01):
            with self.assertRaises(ValueError): encode(v,p)

    def test_address_bases(self):
        self.assertEqual(address_offset(303,1,2),302)
        self.assertEqual(address_offset(302,0,2),302)
        self.assertEqual(address_offset(65536,1),65535)
        for args in [(0,1,1),(65535,0,2),(1,2,1),(True,1,1)]:
            with self.assertRaises(ValueError): address_offset(*args)

    def test_alarm(self):
        state=alarm_state(39)
        self.assertEqual((state['active'],state['unacknowledged'],state['priority'],state['group']), (True,True,1,1))


class ImportTests(unittest.TestCase):
    def options(self):
        return dict(identity=dict(model='synthetic',firmware='v1',application='test'), address_base=1,source='fixture')

    def test_csv_and_xml_explicit_rows(self):
        csv='Technicalname;Description;Modbus reg;Address format;Registertype;Desimals;Min;Max;R/W\nx;Test;303;S32;Holding;1;-100;100;R/W\n'
        doc=import_rows(csv,'csv',**self.options())
        p=load_map(json.dumps(doc))[1][0]
        self.assertEqual((p.address,p.offset,p.kind,p.access),(303,302,'s32','RW'))
        xml='<Points><Point Technicalname="x"><Description>Test</Description><ModbusReg>1</ModbusReg><AddressFormat>U16</AddressFormat></Point></Points>'
        self.assertEqual(import_rows(xml,'xml',**self.options())['points'][0]['address'],1)

    def test_rejected_rows_preserved(self):
        xml='<Map><Point key="x" name="x" address="1" kind="u16"/><Point key="bad" name="unknown" id="201" kind="u16"/></Map>'
        result=import_rows(xml,'xml',**self.options())
        self.assertEqual(len(result['points']),1)
        self.assertEqual(result['rejected_rows'][0]['original']['id'],'201')

    def test_no_guess_or_xml_entities(self):
        for xml in ['<Map><Point name="outdoor" id="201"/></Map>',
                    '<!DOCTYPE x [<!ENTITY a "test">]><Map/>','<Vendor><Unknown/></Vendor>']:
            with self.assertRaises(ValueError): import_rows(xml,'xml',**self.options())

    def test_map_identity_duplicates(self):
        doc,_,_=fixture()
        doc['points'].append(doc['points'][0])
        with self.assertRaises(ValueError): load_map(json.dumps(doc))
        doc['identity']['application']=''
        with self.assertRaises(ValueError): load_map(json.dumps(doc))


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.model=sim.Model()
        self.audit=[]
        self.client=Client('synthetic',audit=self.audit.append)
        self.mock=patch('socket.create_connection',side_effect=lambda *a,**kw:WireSocket(self.model))
        self.mock.start();self.addCleanup(self.mock.stop)

    def test_read_input_identify_exception_and_echo(self):
        self.assertEqual(self.client.read(0),[7])
        self.assertEqual(self.client.read(0,function=4),[23])
        self.assertIn('SIMULATOR',self.client.identify()['objects']['0'])
        with self.assertRaises(ModbusError): self.client.read(80)
        self.assertEqual(self.audit[-1]['exception_code'],2)
        self.assertTrue(self.audit[-1]['modbus_response'])
        self.assertFalse(self.audit[-1]['success'])
        self.client.write(0,[1],6)
        self.assertEqual(self.client.read(0),[1])
        self.client.write(1,[65535,65413],16)
        self.assertEqual(self.client.read(1,2),[65535,65413])

    def test_identification_golden_pdu(self):
        # Protocol specification header: fc, MEI, read ID, conformity, more,
        # next object, object count; then object ID, length, bytes.
        pdu = bytes.fromhex('2b0e0101000001000441434d45')
        def golden(packet):
            return packet[:4] + struct.pack('>H', len(pdu)+1) + packet[6:7] + pdu
        with patch('socket.create_connection', return_value=WireSocket(self.model,golden)):
            self.assertEqual(self.client.identify(),dict(objects={'0':'ACME'},more_follows=0,next_object=0))

    def test_reject_malformed_responses(self):
        for mutate in [lambda b:b'\x00\x99'+b[2:], lambda b:b[:6]+b'\x02'+b[7:],
                       lambda b:b[:2]+b'\x00\x01'+b[4:],lambda b:b[:-1],
                       lambda b:b[:8]+b'\x04'+b[9:],lambda b:b[:7]+b'\x04'+b[8:]]:
            with patch('socket.create_connection',return_value=WireSocket(self.model,mutate)):
                with self.assertRaises(ModbusError):self.client.read(0)
                self.assertFalse(self.audit[-1]['success'])

    def test_tcp_open_is_not_modbus_success_and_timeout_logged(self):
        with patch('socket.create_connection',return_value=WireSocket(self.model, lambda b:b'')):
            with self.assertRaises(ModbusError):self.client.read(0)
        self.assertTrue(self.audit[-1]['tcp_connected'])
        self.assertFalse(self.audit[-1]['modbus_response'])
        with patch('socket.create_connection',side_effect=socket.timeout('synthetic timeout')):
            with self.assertRaises(socket.timeout):self.client.read(0)
        self.assertIn('timeout',self.audit[-1]['error'])

    def session(self, enabled=True, policy_change=None):
        doc, points, policy=fixture()
        if policy_change:policy_change(policy)
        return Session(self.client,doc,points,policy,enabled)

    def test_write_gates_before_network(self):
        for session in [self.session(False),self.session(policy_change=lambda p:p.update(map_sha256='bad')),
                        self.session(policy_change=lambda p:p.update(points={}))]:
            with self.assertRaises(ValueError):session.write('flag',1,6)
        self.assertEqual(self.model.requests,[])
        with self.assertRaises(ValueError):self.session().write_test('flag',1,disconnected=False)
        with self.assertRaises(ValueError):self.session().write('target',1,6)
        self.assertEqual(self.model.requests,[])

    def test_original_outside_map_bounds_stops_test(self):
        self.model.holding[0]=7
        with self.assertRaises(ValueError):self.session().write_test('flag',1,6,True)
        self.assertTrue(all(p[0] in (3,4) for p in self.model.requests))

    def test_u16_and_s32_test_restore(self):
        self.model.holding[0]=0
        s=self.session()
        for key,value,fc in [('flag',1,6),('flag',1,16),('target',-14.2,16)]:
            original=dict(self.model.holding)
            result=s.write_test(key,value,fc,True)
            self.assertTrue(result['success'])
            self.assertEqual(self.model.holding,original)
            self.assertEqual(result['display_comparison'],'not performed')

    def test_timeout_after_write_still_restores(self):
        self.model.holding[0]=0
        self.model.drop_after_write=True
        result=self.session().write_test('flag',1,6,True)
        self.assertFalse(result['success'])
        self.assertTrue(result['restored'])
        self.assertEqual(self.model.holding[0],0)

    def test_manual_mode_restored(self):
        doc,points,policy=fixture()
        points[0]=replace(points[0],manual_reg=4)
        manual=Point('manual','Manual',4,1,'u16',minimum=0,maximum=1,access='RW',source='fixture')
        points.append(manual)
        doc['points']=[asdict(p) for p in points]
        policy.update(map_sha256=map_digest(doc))
        policy['points']['manual']=dict(documentation='fixture',reviewed_by='test')
        self.model.holding[0]=0
        result=Session(self.client,doc,points,policy,True).write_test('flag',1,6,True)
        self.assertTrue(result['success'])
        self.assertEqual((self.model.holding[0],self.model.holding[3]),(0,0))

    def test_lost_audit_storage_does_not_block_raw_restore(self):
        self.model.holding[0]=0
        def disk_failure(event):
            if self.model.holding[0] == 1 or event.get('phase', '').startswith('restore_'):
                raise OSError('synthetic disk full')
            self.audit.append(event)
        self.client.audit=disk_failure
        result=self.session().write_test('flag',1,6,True)
        self.assertTrue(result['restored'])
        self.assertFalse(result['success'])
        self.assertEqual(self.model.holding[0],0)
        self.assertTrue(result['audit_errors'])

    def test_restore_failure_reported(self):
        self.model.holding[0]=0
        session=self.session()
        original_put=session._put
        def fail_restore(p,words,fc,phase):
            if phase=='restore_value':raise OSError('synthetic disconnected')
            original_put(p,words,fc,phase)
        with patch.object(session,'_put',side_effect=fail_restore):
            result=session.write_test('flag',1,6,True)
        self.assertFalse(result['restored'])
        self.assertFalse(result['success'])
        self.assertIn('RESTORE VALUE FAILED',result['errors'][0])

    def test_audit_failure_prevents_write(self):
        self.model.holding[0]=0
        session=self.session()
        self.client.audit=None
        with self.assertRaises(ValueError):session.write('flag',1,6)
        self.assertTrue(all(p[0] in (3,4) for p in self.model.requests))


class TcpLoopbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.server=sim.Server(('127.0.0.1',0))
        except PermissionError as err:
            if os.environ.get('OUFLEX_REQUIRE_TCP') == '1':
                raise
            raise unittest.SkipTest('Environment denies loopback socket binding: '+str(err))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_real_tcp_read_write_restore_and_identification(self):
        c=Client('127.0.0.1',self.server.server_address[1],audit=lambda e:None)
        doc,points,policy=fixture()
        self.assertEqual(c.read(0),[7])
        self.assertIn('SIMULATOR',c.identify()['objects']['0'])
        result=Session(c,doc,points,policy,True).write_test('target',-55.5,16,True)
        self.assertTrue(result['success'])

    def test_real_timeout_and_bad_transaction(self):
        c=Client('127.0.0.1',self.server.server_address[1],timeout=.05)
        self.server.model.delay=.15
        try:
            with self.assertRaises(socket.timeout):c.read(0)
        finally:self.server.model.delay=0
        self.server.model.bad_transaction=True
        try:
            with self.assertRaises(ModbusError):c.read(0)
        finally:self.server.model.bad_transaction=False



class CliTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('ouflex_cli',ROOT/'tools/ouflex_lab.py')
        self.cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.cli)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        doc,_,policy=fixture()
        (self.dir/'map.json').write_text(json.dumps(doc))
        (self.dir/'policy.json').write_text(json.dumps(policy))
        self.model=sim.Model()
        self.socket_patch=patch('socket.create_connection',side_effect=lambda *a,**k:WireSocket(self.model))
        self.socket_patch.start();self.addCleanup(self.socket_patch.stop)

    def run_command(self,command,*args):
        parsed=self.cli.build_parser().parse_args([command,*args])
        return self.cli.execute(parsed)

    def network(self):
        return ['--host','synthetic','--audit',str(self.dir/'audit.jsonl'),'--out',str(self.dir/'out.json')]

    def test_backup_and_single_restore(self):
        args=self.network()+['--map',str(self.dir/'map.json')]
        result=self.run_command('backup',*args)
        self.assertTrue(result['complete'])
        (self.dir/'snapshot.json').write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            self.run_command('backup',*args)
        self.model.holding[1]=0;self.model.holding[2]=0
        result=self.run_command('restore',*args,'--policy',str(self.dir/'policy.json'),
            '--snapshot',str(self.dir/'snapshot.json'),'--key','target',
            '--enable-write-tests','--confirm-disconnected')
        self.assertTrue(result['success'])
        self.assertEqual(self.model.holding[2],65413)
        with self.assertRaises(ValueError):
            self.run_command('restore',*args,'--policy',str(self.dir/'policy.json'),
                '--snapshot',str(self.dir/'snapshot.json'),'--key','target')

    def test_capture_export_report_compare(self):
        result=self.run_command('capture-map',*self.network(),'--map',str(self.dir/'map.json'))
        self.assertEqual(result[1]['interpreted'],-12.3)
        self.run_command('export',str(self.dir/'audit.jsonl'),'--json',str(self.dir/'all.json'),'--csv',str(self.dir/'all.csv'))
        report=self.run_command('report',str(self.dir/'audit.jsonl'),'--out',str(self.dir/'report.json'))
        self.assertEqual(report['tcp_connections'],2)
        result=self.run_command('compare',str(self.dir/'out.json'),str(self.dir/'out.json'),'--out',str(self.dir/'changes.json'))
        self.assertEqual(result['changes'],0)

if __name__=='__main__':unittest.main()
