"""Shared CLI/UI service. All controller access is serialized by the HTTP server."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import socket

from custom_components.ouman_ouflex.modbus import Client
from custom_components.ouman_ouflex.ounet import import_ounet
from custom_components.ouman_ouflex.pointmap import load_map, map_digest, encode, decode
from custom_components.ouman_ouflex.session import Session
from tools.ouflex_lab import journal


class Workbench:
    def __init__(self, host, port=502, unit=1, audit='ouflex-results/tool-audit.jsonl',
                 policy=None, transport='socket'):
        self.client = Client(host, port, unit, timeout=2, audit=journal(audit), transport=transport)
        self.audit_path = Path(audit)
        self.policy = policy or {}
        self.doc, self.points = None, []

    def import_map(self, text, firmware='2.3.3'):
        doc = import_ounet(text, firmware=firmware) if text.lstrip('\ufeff \n').startswith('<') else json.loads(text)
        self.doc, self.points = load_map(json.dumps(doc))
        return self.state()

    def state(self):
        return dict(endpoint=dict(host=self.client.host, port=self.client.port, unit=self.client.unit),
                    identity=self.doc['identity'] if self.doc else None,
                    digest=map_digest(self.doc) if self.doc else None,
                    lcd_rename_supported=False,
                    points=[dict(asdict(p), writable=self.allowed(p)) for p in self.points])

    def evidence(self, p):
        e = self.policy.get('points', {}).get(p.key, {})
        # Only the two numeric operations independently reported in issue #34.
        shape = {2: ('u16', 0, 6), 395: ('s32', 1, 16)}.get(p.address)
        if (not self.doc or self.doc['identity'] != {'model': 'Ouflex', 'firmware': '2.3.3', 'application': '1.1.2'}
                or self.policy.get('map_sha256') != map_digest(self.doc)
                or self.policy.get('endpoint') != dict(host=self.client.host, port=self.client.port, unit=self.client.unit)
                or p.address_base != 1 or p.area != 'holding' or p.manual_reg is not None
                or p.byte_order != 'big' or p.word_order != 'big'
                or not shape or (p.kind, p.decimals, e.get('function')) != shape
                or e.get('physically_verified') is not True
                or not all(e.get(k) for k in ('documentation', 'reviewed_by', 'meaning', 'bounds_evidence'))
                or e.get('minimum') != p.minimum or e.get('maximum') != p.maximum
                or p.minimum is None or p.maximum is None
                or p.metadata.get('operation', 'value') != 'value'):
            raise ValueError('No matching verified numeric write authorization for this point/map/endpoint')
        return e

    def allowed(self, p):
        try:
            self.evidence(p)
            return True
        except ValueError:
            return False

    def session(self):
        return Session(self.client, self.doc, self.points)

    def read(self, keys):
        if not isinstance(keys, list) or not 1 <= len(keys) <= 32 or len(set(keys)) != len(keys):
            raise ValueError('Select 1..32 distinct points per read')
        result = []
        for key in keys:
            try:
                raw, value = self.session().read(key)
                result.append(dict(key=key, raw=raw, value=value))
            except Exception as err:
                result.append(dict(key=key, error=str(err)))
                # Do not spend minutes polling a disconnected controller.
                if not self.client.events or not self.client.events[-1].get('modbus_response'):
                    break
        self.client.events.clear()
        return result

    def write(self, key, value, *, disconnected=False, test=False):
        if disconnected is not True:
            raise ValueError('Confirm physical disconnection before writing')
        session = self.session()
        p = session.point(key)
        e = self.evidence(p)
        # Imported access levels never become write permissions automatically.
        writable = replace(p, access='RW')
        doc = dict(self.doc, points=[asdict(writable if x.key == key else x) for x in self.points])
        policy = dict(map_sha256=map_digest(doc), identity=doc['identity'], points={key:e})
        session = Session(self.client, doc, [writable], policy, enabled=True, physical=True)
        if test:
            return session.write_test(key, value, e['function'], disconnected=True)
        # Snapshot is durable before a send. A lost acknowledgement can mean a successful write.
        words = encode(value, writable)
        original, old = session.read(key)
        if encode(old, writable) != original:
            raise ValueError('Original value outside verified bounds/representation')
        session._journal('original', key=key, raw=original)
        try:
            session._put(writable, words, e['function'], 'write')
            return dict(success=True, key=key, original=original, value=decode(words, writable))
        except Exception as err:
            result = dict(success=False, error=str(err), restored=False, original=original)
            try:
                session._put(writable, original, e['function'], 'restore_value')
                result['restored'] = True
            except Exception as restore:
                result['restore_error'] = str(restore)
            result['audit_errors'] = session.audit_errors
            return result
        finally:
            self.client.events.clear()

    def audit(self):
        if not self.audit_path.exists():
            return []
        # Bound response size even after years of use.
        with self.audit_path.open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size-100000))
            if size > 100000:
                stream.readline()
            return [json.loads(line) for line in stream.read().decode().splitlines()][-100:]

    def probe(self):
        result = []
        for port in (503, 504, 505):
            row = dict(port=port, protocol='unknown', request_hex='')
            try:
                # Passive banner only: unknown services receive no guessed RPC payload.
                with socket.create_connection((self.client.host, port), 1) as sock:
                    row['connected'] = True
                    sock.settimeout(1)
                    row['banner_hex'] = sock.recv(256).hex()
            except OSError as err:
                row['error'] = str(err)
            self.client.audit(dict(operation='passive_probe', host=self.client.host, **row))
            result.append(row)
        return result
