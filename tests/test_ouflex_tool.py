"""Workbench tests exercise the real transport framing against the shared simulator."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from custom_components.ouman_ouflex.pointmap import Point, map_digest
from tools.ouflex_simulator import Model
from tools.ouflex_tool.core import Workbench


class Socket:
    def __init__(self, model):
        self.model = model
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def settimeout(self, value):
        pass
    def sendall(self, request):
        tid, proto, length, unit = struct.unpack('>HHHB', request[:7])
        pdu = self.model.reply(request[7:])
        self.response = struct.pack('>HHHB', tid, 0, len(pdu)+1, unit)+pdu
    def recv(self, count):
        # Fragmented responses exercise the actual Client._exact implementation.
        result, self.response = self.response[:min(count,3)], self.response[min(count,3):]
        return result


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Workbench('127.0.0.1', audit=Path(self.tmp.name)/'audit.jsonl')
        self.points = [Point('year','Vuosi',2,1,'u16',minimum=2008,maximum=2100,source='XML'),
                       Point('room','Huonelämpötilan asetusarvo',395,1,'s32',decimals=1,
                             minimum=5,maximum=35,source='XML'),
                       Point('measurement','L1 menoveden lämpötila',203,1,'s32',decimals=1)]
        self.doc = dict(schema_version=1,identity=dict(model='Ouflex',firmware='2.3.3',application='1.1.2'),
                        points=[asdict(p) for p in self.points])
        self.app.import_map(json.dumps(self.doc))
        self.app.policy = dict(map_sha256=map_digest(self.app.doc), endpoint=self.app.state()['endpoint'],points={
            p.key: dict(function=6 if p.kind=='u16' else 16,physically_verified=True,
                        minimum=p.minimum,maximum=p.maximum,documentation='Issue #34 user observation',
                        reviewed_by='test fixture',meaning=p.name,bounds_evidence='synthetic XML')
            for p in self.points[:2]})
        self.model = Model()
        self.model.holding.update({1:2026,394:0,395:210,202:0,203:200})
        self.mock = patch('socket.create_connection',side_effect=lambda *a,**k: Socket(self.model))
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_read_and_decode(self):
        self.assertEqual([r['value'] for r in self.app.read(['year','room'])],[2026,21])
        self.assertTrue(all(r[0]==3 for r in self.model.requests))

    def test_fc06_and_fc16_write_test_restore(self):
        for key, value, offset, original, fc in [('year',2027,1,2026,6),('room',21.1,395,210,16)]:
            result=self.app.write(key,value,test=True,disconnected=True)
            self.assertTrue(result['success'],result)
            self.assertTrue(result['restored'])
            self.assertEqual(self.model.holding[offset],original)
            self.assertIn(fc,[r[0] for r in self.model.requests])
        self.assertTrue(any(r.get('phase')=='test_complete' for r in self.app.audit()))

    def test_persistent_write(self):
        self.assertTrue(self.app.write('room',21.1,disconnected=True)['success'])
        self.assertEqual(self.model.holding[395],211)

    def test_unknown_measurement_and_confirmation_rejected_before_io(self):
        for key, confirm in [('measurement',True),('room',False)]:
            with self.assertRaises(ValueError):self.app.write(key,22,disconnected=confirm)
        self.assertEqual(self.model.requests,[])

    def test_bounds_precision_nonfinite(self):
        for value in (4,36,21.11,'NaN','Infinity'):
            with self.assertRaises(ValueError):self.app.write('room',value,disconnected=True)
        self.assertEqual(self.model.requests,[])

    def test_map_endpoint_and_function_bound(self):
        self.app.policy['endpoint']['host']='other'
        self.assertFalse(self.app.allowed(self.points[1]))
        self.app.policy['endpoint']['host']='127.0.0.1'
        self.app.policy['points']['room']['function']=6
        self.assertFalse(self.app.allowed(self.points[1]))
        self.app.policy['points']['room']['function']=16
        altered=dict(self.doc,identity=dict(self.doc['identity'],firmware='other'))
        self.app.import_map(json.dumps(altered))
        self.assertFalse(self.app.allowed(self.points[1]))

    def test_uncertain_write_restores_raw_original(self):
        real=self.app.client.write
        calls=[]
        def uncertain(*args,**kwargs):
            result=real(*args,**kwargs)
            calls.append(1)
            if len(calls)==1:raise TimeoutError('lost acknowledgement')
            return result
        self.app.client.write=uncertain
        result=self.app.write('room',21.1,disconnected=True)
        self.assertFalse(result['success'])
        self.assertTrue(result['restored'])
        self.assertEqual(self.model.holding[395],210)

    def test_durable_audit_failure_prevents_send(self):
        def broken(event):raise OSError('disk full')
        self.app.client.audit=broken
        with self.assertRaises(OSError):self.app.write('room',21.1,disconnected=True)
        self.assertFalse(any(r[0] in (6,16) for r in self.model.requests))

    def test_fc04_and_all_integer_types(self):
        extra=[Point('i'+str(i),'Input',1,0,kind,area='input',decimals=1)
               for i,kind in enumerate(('u16','s16','u32','s32'))]
        self.model.inputs={1:0xffff,2:0xff85}
        self.app.points=extra
        rows=self.app.read([p.key for p in extra])
        self.assertEqual(rows[1]['value'],-.1)
        self.assertEqual(rows[3]['value'],-12.3)
        self.assertTrue(all(r[0]==4 for r in self.model.requests))

    def test_xml_rejects_dtd(self):
        with self.assertRaises(ValueError):self.app.import_map('<!DOCTYPE foo><x/>')

    def test_read_batch_validation(self):
        for keys in ([],['room']*2,['x']*33):
            with self.assertRaises(ValueError):self.app.read(keys)


if __name__=='__main__':unittest.main()

class HTTPTests(unittest.TestCase):
    def request(self, path, payload, headers=None):
        import io
        from types import SimpleNamespace
        from tools.ouflex_tool.server import make_server
        app = unittest.mock.Mock()
        app.state.return_value = dict(points=[])
        with patch('tools.ouflex_tool.server.HTTPServer') as factory:
            make_server(app,8765)
            cls=factory.call_args[0][1]
        handler=object.__new__(cls)
        handler.server=SimpleNamespace(server_port=8765)
        handler.path=path
        handler.request_version='HTTP/1.1'
        handler.requestline='POST '+path+' HTTP/1.1'
        handler.command='POST'
        handler.wfile=io.BytesIO()
        # Recover session token from the authorized page (as a local browser does).
        handler.headers={'Host':'127.0.0.1:8765'}
        handler.path='/'
        handler.do_GET()
        import re
        token=re.search(b"X-Ouflex-Token':'([^']+)'",handler.wfile.getvalue()).group(1).decode()
        handler.path=path
        body=json.dumps(payload).encode()
        handler.rfile=io.BytesIO(body)
        handler.wfile=io.BytesIO()
        handler.headers={'Host':'127.0.0.1:8765','Content-Length':str(len(body)),
                         'Origin':'http://127.0.0.1:8765','X-Ouflex-Token':token}
        handler.headers.update(headers or {})
        handler.do_POST()
        return handler.wfile.getvalue(),app

    def test_state_capability(self):
        response,app=self.request('/api/state',{})
        self.assertIn(b'200 OK',response)
        app.state.assert_called_once()

    def test_cross_origin_and_rebinding_denied(self):
        for headers in ({'Origin':'http://evil.invalid'},{'Host':'evil.invalid'}, {'X-Ouflex-Token':'wrong'}):
            response,app=self.request('/api/write',{},headers)
            self.assertIn(b'403 Forbidden',response)
            app.write.assert_not_called()

    def test_missing_explicit_write_mode_denied(self):
        response,app=self.request('/api/write',dict(key='room',value=22,disconnected=True))
        self.assertIn(b'400 Bad Request',response)
        app.write.assert_not_called()
