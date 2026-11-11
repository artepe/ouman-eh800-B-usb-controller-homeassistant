#!/usr/bin/env python3
"""Ouflex laboratory CLI. Real MBAP TCP I/O; no device register assumptions.

Python 3.9+, macOS/Linux, standard library only. Read operations never write.
"""
from __future__ import annotations
import argparse
import csv
import ftplib
import importlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Package __init__ is deliberately free of Home Assistant imports.
from custom_components.ouman_ouflex.modbus import Client, address_offset
from custom_components.ouman_ouflex.pointmap import (Point, decode, alarm_state, load_map,
                                                    import_rows, map_digest, encode)
from custom_components.ouman_ouflex.session import Session


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def journal(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    def append(event):
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    return append


def records(path):
    text = Path(path).read_text(encoding='utf-8')
    if text.lstrip().startswith('['):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def get_map(args):
    if not args.map:
        raise ValueError('--map required')
    return load_map(Path(args.map).read_text(encoding='utf-8-sig'))


def ftp_fetch(args):
    # User/password are explicit. No credential guessing, upload or deletion.
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    result = dict(ip=args.host, port=args.port, directory='/Files', files=[], errors=[])
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(args.host, args.port, timeout=args.timeout)
            ftp.login(args.username, os.environ.get(args.password_env, ''))
            ftp.cwd('/Files')
            names = ftp.nlst()
            for remote in names[:128]:
                name = remote.rsplit('/', 1)[-1]
                if name in ('', '.', '..') or name != remote or '\\' in name:
                    result['errors'].append('Unsupported remote name: ' + remote)
                    continue
                if Path(name).suffix.lower() not in ('.xml', '.csv', '.json', '.txt', '.modbus'):
                    continue
                target = destination / name
                if target.exists():
                    result['errors'].append('Local file exists: ' + name)
                    continue
                size = 0
                try:
                    with target.open('xb') as stream:
                        def chunk(data):
                            nonlocal size
                            size += len(data)
                            if size > 10_000_000:
                                raise ValueError('FTP file size limit')
                            stream.write(data)
                        ftp.retrbinary('RETR ' + name, chunk)
                    result['files'].append(dict(name=name, bytes=size))
                except Exception as err:
                    result['errors'].append(dict(name=name, error=str(err)))
    except Exception as err:
        result['errors'].append(str(err))
    return result


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    network = ('discover', 'identify', 'read', 'read-block', 'scan', 'write', 'write-test', 'capture-map', 'backup', 'restore')
    for command in network:
        p = sub.add_parser(command)
        p.add_argument('--host', default='192.168.10.105')
        p.add_argument('--port', type=int, default=502)
        p.add_argument('--unit', type=int, default=1)
        p.add_argument('--timeout', type=float, default=2)
        p.add_argument('--audit', default='ouflex-results/audit.jsonl')
        p.add_argument('--out', required=True)
        if command in ('read', 'read-block', 'scan', 'discover'):
            p.add_argument('--address', type=int, required=True,
                           help='Probe address; no default map is assumed')
            p.add_argument('--address-base', type=int, choices=(0, 1), required=True)
            p.add_argument('--function', type=int, choices=(3, 4), default=3)
        if command in ('read-block', 'scan'):
            p.add_argument('--count', type=int, required=True)
        if command == 'scan':
            p.add_argument('--block-size', type=int, default=16)
            p.add_argument('--delay', type=float, default=0.2)
        if command == 'discover':
            p.add_argument('--ports', default='502,503,504,505')
            p.add_argument('--units', default='1', help='Explicit comma separated IDs; at most 16')
        if command in ('write', 'write-test', 'capture-map', 'backup', 'restore'):
            p.add_argument('--map', required=True)
        if command in ('write', 'write-test', 'restore'):
            p.add_argument('--key', required=True, help='Restore accepts only one explicitly selected point')
            if command != 'restore':
                p.add_argument('--value', required=True)
            p.add_argument('--policy', required=True)
            p.add_argument('--function', type=int, choices=(6, 16), default=16)
            p.add_argument('--enable-write-tests', action='store_true')
            p.add_argument('--confirm-disconnected', action='store_true')
        if command == 'restore':
            p.add_argument('--snapshot', required=True)
        if command == 'write-test':
            p.add_argument('--display-note', help='Actual local display observation, if available')
    p = sub.add_parser('decode')
    p.add_argument('words', nargs='+', type=lambda s: int(s, 0))
    p.add_argument('--kind', choices=('u16', 's16', 'u32', 's32'), required=True)
    p.add_argument('--decimals', type=int, default=0)
    p.add_argument('--word-order', choices=('big', 'little'), default='big')
    p.add_argument('--byte-order', choices=('big', 'little'), default='big')
    p.add_argument('--alarm', action='store_true')
    p = sub.add_parser('import-map')
    p.add_argument('input')
    p.add_argument('--format', choices=('xml', 'csv', 'json'), required=True)
    for key in ('model', 'firmware', 'application'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--address-base', type=int, choices=(0, 1), required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('export')
    p.add_argument('input')
    p.add_argument('--json', required=True)
    p.add_argument('--csv', required=True)
    p = sub.add_parser('compare')
    p.add_argument('before')
    p.add_argument('after')
    p.add_argument('--out', required=True)
    p = sub.add_parser('report')
    p.add_argument('input')
    p.add_argument('--map')
    p.add_argument('--out', required=True)
    p = sub.add_parser('map-info')
    p.add_argument('--map', required=True)
    p = sub.add_parser('fetch-map')
    p.add_argument('--host', default='192.168.10.105')
    p.add_argument('--port', type=int, default=21)
    p.add_argument('--timeout', type=float, default=3)
    p.add_argument('--username', required=True)
    p.add_argument('--password-env', default='OUFLEX_FTP_PASSWORD')
    p.add_argument('--destination', required=True)
    p.add_argument('--out', required=True)
    return parser


def execute(args):
    command = args.command
    if command == 'decode':
        p = Point('decode', 'Decode', 0, 0, args.kind, decimals=args.decimals,
                  byte_order=args.byte_order, word_order=args.word_order)
        value = decode(args.words, p)
        return alarm_state(value) if args.alarm else dict(raw=args.words, interpreted=value)
    if command == 'import-map':
        result = import_rows(Path(args.input).read_text(encoding='utf-8-sig'), args.format,
                             identity={k: getattr(args, k) for k in ('model', 'firmware', 'application')},
                             address_base=args.address_base, source=str(args.input))
        save(args.out, result)
        return dict(points=len(result['points']), rejected=result.get('rejected_rows', []),
                    map_sha256=map_digest(load_map(json.dumps(result))[0]))
    if command == 'map-info':
        doc, points = get_map(args)
        return dict(identity=doc['identity'], map_sha256=map_digest(doc), points=len(points),
                    writable_documented=[p.key for p in points if p.access == 'RW'])
    if command == 'fetch-map':
        result = ftp_fetch(args)
        save(args.out, result)
        return result
    if command == 'export':
        rows = records(args.input)
        save(args.json, rows)
        keys = sorted({key for row in rows for key in row})
        with Path(args.csv).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                                 for k, v in row.items()})
        return dict(rows=len(rows))
    if command == 'compare':
        def keyed(path):
            return {(r.get('ip'), r.get('port'), r.get('unit_id'), r.get('function_code'),
                     r.get('address'), r.get('count'), r.get('point_name')): r
                    for r in records(path) if r.get('function_code') in (3, 4)}
        before, after = keyed(args.before), keyed(args.after)
        changes = [dict(identity=list(k), before=before.get(k), after=after.get(k))
                   for k in before.keys() | after.keys()
                   if (before.get(k, {}).get('raw'), before.get(k, {}).get('success')) !=
                      (after.get(k, {}).get('raw'), after.get(k, {}).get('success'))]
        save(args.out, changes)
        return dict(changes=len(changes))
    if command == 'report':
        rows = records(args.input)
        result = dict(records=len(rows), successful_reads=sum(r.get('success', False) for r in rows
                      if r.get('function_code') in (3, 4)),
                      valid_modbus_responses=sum(r.get('modbus_response', False) for r in rows),
                      tcp_connections=sum(r.get('tcp_connected', False) for r in rows),
                      exceptions=[r for r in rows if r.get('exception_code') is not None],
                      failures=[r for r in rows if r.get('error')],
                      writes=[r for r in rows if r.get('function_code') in (6, 16)],
                      transactions=[r for r in rows if r.get('operation') == 'write_transaction'],
                      limitation='Observed responses only; unknown register meanings and absent application features remain unconfirmed')
        if args.map:
            doc, points = get_map(args)
            result.update(identity=doc['identity'], map_sha256=map_digest(doc), points=doc['points'])
        save(args.out, result)
        return result
    audit = journal(args.audit)
    client = Client(args.host, args.port, args.unit, args.timeout, audit)
    if command == 'backup':
        if Path(args.out).exists():
            raise ValueError('Backup destination already exists; original snapshot will not be overwritten')
        doc, points = get_map(args)
        snapshot = dict(schema_version=1, kind='register_snapshot_not_firmware',
                        identity=doc['identity'], map_sha256=map_digest(doc),
                        endpoint=dict(host=args.host, port=args.port, unit=args.unit), points={})
        for p in points:
            try:
                raw = client.read(p.offset, p.count, p.function, name=p.name, datatype=p.kind, decoder=lambda raw: decode(raw, p))
                snapshot['points'][p.key] = dict(raw=raw, interpreted=decode(raw, p),
                                                timestamp=client.events[-1]['timestamp'])
            except Exception as err:
                snapshot['points'][p.key] = dict(error=str(err))
            time.sleep(0.2)
        snapshot['complete'] = all('raw' in r for r in snapshot['points'].values())
        save(args.out, snapshot)
        return snapshot
    if command == 'restore':
        if not args.enable_write_tests or not args.confirm_disconnected:
            raise ValueError('Restore requires both explicit write and disconnection flags')
        doc, points = get_map(args)
        snapshot = json.loads(Path(args.snapshot).read_text(encoding='utf-8'))
        if (snapshot.get('kind') != 'register_snapshot_not_firmware'
            or snapshot.get('identity') != doc['identity']
            or snapshot.get('map_sha256') != map_digest(doc)
            or snapshot.get('endpoint') != dict(host=args.host, port=args.port, unit=args.unit)):
            raise ValueError('Snapshot kind/identity/map/endpoint mismatch')
        session = Session(client, doc, points, json.loads(Path(args.policy).read_text()), enabled=True)
        p = session.permitted(args.key)
        words = snapshot['points'][p.key]['raw']
        value = decode(words, p)
        if encode(value, p) != words:
            raise ValueError('Snapshot value is not exactly representable inside documented bounds')
        result = session.write(p.key, value, args.function)
        save(args.out, result)
        return result
    if command in ('write', 'write-test'):
        if not args.enable_write_tests or not args.confirm_disconnected:
            raise ValueError('Both --enable-write-tests and --confirm-disconnected required before network writes')
        doc, points = get_map(args)
        session = Session(client, doc, points, json.loads(Path(args.policy).read_text()), enabled=True)
        if command == 'write-test':
            result = session.write_test(args.key, args.value, args.function, True, args.display_note)
        else:
            result = session.write(args.key, args.value, args.function)
        save(args.out, result)
        return result
    if command == 'capture-map':
        doc, points = get_map(args)
        for p in points:
            try:
                raw = client.read(p.offset, p.count, p.function, name=p.name, datatype=p.kind, decoder=lambda raw: decode(raw, p))
                event = dict(client.events[-1], interpreted=decode(raw, p),
                             documented_address=p.address, documented_base=p.address_base,
                             map_sha256=map_digest(doc))
                client.events[-1] = event
            except Exception:
                pass  # Complete failure event already durably logged by transport.
            time.sleep(0.2)
        result = client.events
    elif command == 'discover':
        ports, units = [int(v) for v in args.ports.split(',')], [int(v) for v in args.units.split(',')]
        if len(ports) > 4 or len(units) > 16:
            raise ValueError('Discovery limited to 4 ports and 16 explicit Unit IDs')
        result = []
        for port in ports:
            for unit in units:
                probe = Client(args.host, port, unit, args.timeout, audit)
                try:
                    probe.read(address_offset(args.address, args.address_base), 1, args.function)
                except Exception:
                    pass
                result.extend(probe.events)
                time.sleep(0.2)
    elif command == 'identify':
        try:
            client.identify()
        except Exception:
            pass
        result = client.events
    else:
        count = getattr(args, 'count', 1)
        offset = address_offset(args.address, args.address_base, count)
        if command == 'scan':
            if not 1 <= count <= 4096 or not 1 <= args.block_size <= 125 or not 0.05 <= args.delay <= 10:
                raise ValueError('Scan limited to 4096 words, blocks 1..125, delay .05..10s')
            size = args.block_size
        else:
            if count > 125:
                raise ValueError('Read block limited to 125 registers')
            size = count
        for pos in range(offset, offset+count, size):
            try:
                client.read(pos, min(size, offset+count-pos), args.function)
            except Exception:
                pass
            if command == 'scan':
                time.sleep(args.delay)
        result = client.events
    save(args.out, result)
    return result


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, list) and any(not r.get('success', False) for r in result):
            return 1
        if isinstance(result, dict) and (result.get('errors') or result.get('success') is False or result.get('complete') is False):
            return 1
        return 0
    except Exception as err:
        if getattr(args, 'out', None) and not Path(args.out).exists():
            save(args.out, dict(success=False, error=str(err), command=args.command))
        print(json.dumps(dict(error=str(err)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
