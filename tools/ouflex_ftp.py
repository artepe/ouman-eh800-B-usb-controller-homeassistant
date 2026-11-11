#!/usr/bin/env python3
"""Bounded anonymous read-only Ouflex FTP inventory via curl (macOS LAN permissions).

Never sends STOR, DELE, SITE or vendor commands. Special directories are listed
only, never retrieved. Device evidence stays private under ouflex-results/.
"""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
from urllib.parse import quote


def fetch(host, remote, *, listing=False, limit=10_000_000):
    ipaddress.IPv4Address(host)
    if not 0 < limit <= 10_000_000:
        raise ValueError('FTP limit must be 1..10000000 bytes')
    if not remote.startswith('/') or any(c in remote for c in '\r\n\\') or '..' in remote.split('/'):
        raise ValueError('Unsafe FTP path')
    command = ['curl', '--silent', '--show-error', '--fail', '--connect-timeout', '3',
               '--max-time', '10', '--max-filesize', str(limit)]
    if listing:
        command.append('--list-only')
    command.append('ftp://' + host + quote(remote, safe='/'))
    result = subprocess.run(command, capture_output=True, timeout=12)
    if result.returncode:
        raise OSError(result.stderr.decode('utf-8', 'replace'))
    if len(result.stdout) > limit:
        raise ValueError('FTP byte budget exceeded')
    return result.stdout


def collect(host, root):
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest = {'kind': 'read_only_ftp_not_recovery_image', 'files': {}, 'listings': {}, 'errors': []}
    budget = 0
    for directory in ('/', '/files/', '/debug/', '/commands/', '/updates/', '/new_application/', '/rammount/'):
        try:
            names = fetch(host, directory, listing=True).decode('utf-8').splitlines()
            if len(names) > 512:
                raise ValueError('Too many FTP entries')
            manifest['listings'][directory] = names
            # Do not RETR from the command/update staging directories.
            if directory not in ('/', '/files/', '/debug/'):
                continue
            for name in names:
                if not name or name in ('.', '..') or any(c in name for c in '/\\\r\n'):
                    raise ValueError('Unsafe FTP entry')
                if directory == '/' and name not in ('deviceversion.txt', 'modulereport.txt', 'lastupdate.txt'):
                    continue
                remote = directory + name
                data = fetch(host, remote, limit=min(10_000_000, 32_000_000-budget))
                budget += len(data)
                target = root / remote.lstrip('/')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                manifest['files'][remote] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        except (OSError, ValueError, subprocess.TimeoutExpired) as err:
            manifest['errors'].append({'directory': directory, 'error': str(err)})
            # A transport failure requires investigation, not further automatic requests.
            break
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='192.168.10.105')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = collect(args.host, args.out)
    print(json.dumps({'files': len(result['files']), 'errors': result['errors']}))
    raise SystemExit(bool(result['errors']))
