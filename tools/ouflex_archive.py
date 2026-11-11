#!/usr/bin/env python3
"""Read-only Ouflex evidence archive; never a claim of recoverable firmware.

Standard library only. No serial port opens, vendor commands or device writes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import ftplib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.ouman_ouflex.modbus import Client


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def store(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def validate_plan(plan):
    if not isinstance(plan, list) or len(plan) > 256:
        raise ValueError('Plan must be a list of at most 256 explicit read ranges')
    budget = 0
    for r in plan:
        if set(r) != {'port', 'unit', 'function', 'address', 'count'}:
            raise ValueError('Each range requires port/unit/function/address/count (zero based)')
        if any(type(v) is not int for v in r.values()):
            raise ValueError('Read range fields must be integers')
        if not (r['port'] in (502, 503, 504, 505) and 1 <= r['unit'] <= 255
                and r['function'] in (3, 4) and 1 <= r['count'] <= 4096
                and 0 <= r['address'] < r['address'] + r['count'] <= 65536):
            raise ValueError('Invalid read range')
        budget += r['count']
    if budget > 16384:
        raise ValueError('Maximum 16384 words per collection')
    return plan


def usb_inventory():
    # OS inventory only: does not claim an attached device is the target Ouflex.
    if platform.system() == 'Darwin':
        command = ['/usr/sbin/system_profiler', 'SPUSBDataType', '-json']
    elif platform.system() == 'Linux':
        entries = []
        for device in sorted(Path('/sys/bus/usb/devices').glob('*')):
            item = {'sysfs': device.name}
            for field in ('idVendor', 'idProduct', 'manufacturer', 'product', 'serial',
                          'bDeviceClass', 'bNumConfigurations', 'busnum', 'devnum'):
                try:
                    item[field] = (device / field).read_text().strip()
                except OSError:
                    pass
            try:
                item['descriptors_hex'] = (device / 'descriptors').read_bytes().hex()
            except OSError:
                pass
            if 'idVendor' in item:
                entries.append(item)
        return {'scope': 'host USB inventory; target association unconfirmed', 'devices': entries}
    else:
        return {'error': 'USB inventory supports macOS/Linux only'}
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        return {'command': command, 'returncode': run.returncode,
                'stdout': run.stdout, 'stderr': run.stderr}
    except (OSError, subprocess.TimeoutExpired) as err:
        return {'error': str(err)}


def ftp_archive(root, host, username, password, remote_root='/files', timeout=3,
                max_files=512, max_bytes=64*1024*1024):
    """MLSD + RETR, binary-safe; refuse traversal, symlinks, unbounded listings.

    Limits cover attempted files, directory entries and received bytes, including
    partial transfers. No filename filtering: application binaries are preserved.
    """
    report = {'root': remote_root, 'files': [], 'errors': [], 'bytes_received': 0,
              'complete': False}
    if not remote_root.startswith('/') or '..' in PurePosixPath(remote_root).parts or any(
            c in remote_root for c in '\r\n\\'):
        raise ValueError('Invalid absolute FTP root')
    deadline = time.monotonic() + 300
    with ftplib.FTP() as ftp:
        ftp.connect(host, 21, timeout=timeout)
        ftp.login(username, password)
        pending = [(remote_root, Path('ftp'), 0)]
        entries = attempts = 0
        while pending:
            remote, local, depth = pending.pop()
            if time.monotonic() > deadline:
                report['errors'].append('FTP duration limit'); break
            try:
                for name, facts in ftp.mlsd(remote):
                    entries += 1
                    if entries > 2048 or time.monotonic() > deadline:
                        raise ValueError('FTP listing/time limit')
                    if name in ('.', '..') and facts.get('type') in ('cdir', 'pdir'):
                        continue
                    if not name or name in ('.', '..') or any(c in name for c in '/\\\r\n'):
                        raise ValueError('Unsafe remote name')
                    source = remote.rstrip('/') + '/' + name
                    target = root / local / name
                    kind = facts.get('type')
                    if kind == 'dir':
                        if depth >= 8:
                            raise ValueError('FTP depth limit')
                        pending.append((source, local / name, depth + 1))
                    elif kind == 'file':
                        attempts += 1
                        if attempts > max_files:
                            raise ValueError('FTP file count limit')
                        if int(facts.get('size', '0')) > max_bytes - report['bytes_received']:
                            raise ValueError('FTP byte budget exceeded')
                        target.parent.mkdir(parents=True, exist_ok=True)
                        partial = target.with_name(target.name + '.partial')
                        try:
                            with partial.open('xb') as stream:
                                def receive(data):
                                    report['bytes_received'] += len(data)
                                    if report['bytes_received'] > max_bytes or time.monotonic() > deadline:
                                        raise ValueError('FTP byte/time budget exceeded')
                                    stream.write(data)
                                ftp.retrbinary('RETR ' + source, receive)
                            size = partial.stat().st_size
                            if 'size' in facts and size != int(facts['size']):
                                raise ValueError('FTP advertised size mismatch')
                            if target.exists():
                                raise ValueError('Local path collision')
                            partial.rename(target)
                            report['files'].append({'remote': source, 'local': str(local/name),
                                                    'facts': facts, 'bytes': size})
                        except Exception:
                            # Abort session after a failed transfer; control channel may be out of sync.
                            raise
                    elif kind not in ('cdir', 'pdir'):
                        report['errors'].append({'remote': source, 'error': 'Unsupported type', 'facts': facts})
            except Exception as err:
                report['errors'].append({'remote': remote, 'error': str(err)})
                return report
    report['complete'] = not report['errors']
    return report


def collect(args):
    plan = validate_plan(json.loads(args.plan.read_text()) if args.plan else [])
    if args.ftp_user and args.password_env not in os.environ:
        raise ValueError('FTP password environment variable is missing')
    root = args.out
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    store(root, 'request.json', {'host': args.host, 'plan': plan, 'identify_unit': args.unit,
                              'ftp_requested': bool(args.ftp_user), 'usb_requested': args.usb})
    status = {'schema_version': 1, 'kind': 'evidence_archive_not_firmware_backup',
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'firmware_recovery_verified': False, 'errors': []}
    try:
        probes = []
        for port in (21, 502, 503, 504, 505):
            try:
                with socket.create_connection((args.host, port), args.timeout):
                    probes.append({'port': port, 'tcp_connected': True})
            except OSError as err:
                probes.append({'port': port, 'tcp_connected': False, 'error': str(err)})
        store(root, 'tcp.json', probes)
        for probe in probes:
            if not probe['tcp_connected']:
                status['errors'].append({'operation': 'tcp', **probe})
        def audit(event):
            with (root/'modbus.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        client = Client(args.host, 502, args.unit, args.timeout, audit)
        try:
            client.identify()
        except Exception as err:
            status['errors'].append({'operation': 'identify', 'error': str(err)})
        for r in plan:
            client = Client(args.host, r['port'], r['unit'], args.timeout, audit)
            for address in range(r['address'], r['address'] + r['count'], 32):
                time.sleep(0.2)
                try:
                    client.read(address, min(32, r['address'] + r['count'] - address), r['function'])
                except Exception as err:
                    status['errors'].append({'operation': 'read', 'range': r,
                                             'address': address, 'error': str(err)})
        if args.usb:
            usb = usb_inventory()
            store(root, 'usb.json', usb)
            if usb.get('error') or usb.get('returncode', 0) != 0:
                status['errors'].append({'operation': 'usb', 'error': 'Inventory failed; see usb.json'})
        if args.ftp_user:
            try:
                report = ftp_archive(root, args.host, args.ftp_user,
                                     os.environ[args.password_env], args.ftp_root, args.timeout)
            except Exception as err:
                report = {'complete': False, 'errors': [str(err)]}
            store(root, 'ftp.json', report)
            if not report['complete']:
                status['errors'].append({'operation': 'ftp', 'error': 'Incomplete; see ftp.json'})
    finally:
        status['finished_utc'] = datetime.now(timezone.utc).isoformat()
        status['requested_operations_complete'] = not status['errors']
        store(root, 'status.json', status)
        files = {str(p.relative_to(root)): {'bytes': p.stat().st_size, 'sha256': digest(p)}
                 for p in sorted(root.rglob('*')) if p.is_file()}
        store(root, 'manifest.json', {'schema_version': 1, 'files': files,
                                    'note': 'Integrity only; does not prove completeness or restorability'})
    return 1 if status['errors'] else 0


def verify(root):
    manifest = json.loads((root/'manifest.json').read_text())
    errors = []
    for name, entry in manifest['files'].items():
        path = root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(root.resolve()):
            errors.append(name); continue
        if not path.is_file() or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            errors.append(name)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    errors.extend(sorted(actual - set(manifest['files']) - {'manifest.json'}))
    return {'integrity_ok': not errors, 'errors': errors, 'firmware_recovery_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('collect')
    p.add_argument('--host', default='192.168.10.105')
    p.add_argument('--unit', type=int, choices=range(1, 256), default=1)
    p.add_argument('--timeout', type=float, default=2)
    p.add_argument('--plan', type=Path, help='Explicit zero-based read ranges JSON; none by default')
    p.add_argument('--usb', action='store_true', help='Host OS USB inventory only')
    p.add_argument('--ftp-user')
    p.add_argument('--password-env', default='OUFLEX_FTP_PASSWORD')
    p.add_argument('--ftp-root', default='/files')
    p.add_argument('--out', type=Path, required=True, help='New private directory')
    p = sub.add_parser('verify')
    p.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            result = verify(args.archive)
            print(json.dumps(result))
            return 0 if result['integrity_ok'] else 1
        if not 0 < args.timeout <= 30:
            raise ValueError('Timeout must be in (0, 30]')
        return collect(args)
    except (OSError, ValueError, KeyError, ftplib.Error) as err:
        print(str(err), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
