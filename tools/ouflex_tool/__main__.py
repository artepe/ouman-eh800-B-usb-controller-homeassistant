"""python3 -m tools.ouflex_tool --help"""
import argparse
import json
from pathlib import Path
import sys
from .core import Workbench


def main():
    p = argparse.ArgumentParser(description='Local Ouflex reader and verified numeric editor (stdlib only)')
    p.add_argument('--host', default='192.168.10.105')
    p.add_argument('--port', type=int, default=502)
    p.add_argument('--unit', type=int, default=1)
    p.add_argument('--transport', choices=('socket', 'nc'), default='socket')
    p.add_argument('--map')
    p.add_argument('--firmware', default='2.3.3')
    p.add_argument('--policy')
    p.add_argument('--audit', default='ouflex-results/tool-audit.jsonl')
    sub = p.add_subparsers(dest='command', required=True)
    ui = sub.add_parser('serve')
    ui.add_argument('--http-port', type=int, default=8765)
    sub.add_parser('list')
    read = sub.add_parser('read')
    read.add_argument('keys', nargs='+')
    for name in ('write', 'write-test'):
        cmd = sub.add_parser(name)
        cmd.add_argument('key')
        cmd.add_argument('value')
        cmd.add_argument('--confirm-disconnected', action='store_true')
    sub.add_parser('probe')
    sub.add_parser('policy-template', help='Print exact-map policy for operator review; does not enable it')
    ftp = sub.add_parser('fetch-map', help='Read only the known anonymous FTP description')
    ftp.add_argument('--out', required=True)
    args = p.parse_args()
    try:
        app = Workbench(args.host, args.port, args.unit, args.audit,
                        json.loads(Path(args.policy).read_text()) if args.policy else None, args.transport)
        if args.map:
            app.import_map(Path(args.map).read_text(encoding='utf-8-sig'), args.firmware)
        if args.command == 'fetch-map':
            import ftplib
            target = Path(args.out)
            target.parent.mkdir(parents=True, exist_ok=True)
            with ftplib.FTP() as ftp:
                ftp.connect(args.host, 21, timeout=3)
                ftp.login('anonymous', '')
                chunks = []
                total = 0
                def collect(data):
                    nonlocal total
                    total += len(data)
                    if total > 2_000_000:
                        raise ValueError('XML exceeds 2 MB')
                    chunks.append(data)
                ftp.retrbinary('RETR /files/ounetDescrFile_fi-FI.xml', collect)
            text = b''.join(chunks).decode('utf-8-sig')
            app.import_map(text, args.firmware)
            with target.open('x', encoding='utf-8') as stream:
                stream.write(text)
            print(json.dumps(dict(points=len(app.points), file=str(target))))
            return 0
        if args.command == 'policy-template':
            if not app.doc:
                raise ValueError('--map required')
            result = dict(map_sha256=app.state()['digest'], endpoint=app.state()['endpoint'], points={})
            for point in app.points:
                if point.address not in (2, 395):
                    continue
                result['points'][point.key] = dict(
                    function=6 if point.address == 2 else 16,
                    minimum=point.minimum, maximum=point.maximum,
                    meaning=point.name, documentation='GitHub issue #34: user-reported physical test',
                    bounds_evidence='Imported Ounet XML min/max; review for this installation',
                    reviewed_by='', physically_verified=False)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'serve':
            from .server import serve
            serve(app, args.http_port)
            return 0
        if args.command == 'list':
            result = app.state()
        elif args.command == 'read':
            result = app.read(args.keys)
        elif args.command == 'probe':
            result = app.probe()
        else:
            result = app.write(args.key, args.value, disconnected=args.confirm_disconnected,
                               test=args.command == 'write-test')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int((isinstance(result, dict) and result.get('success') is False) or
                   (isinstance(result, list) and any('error' in row for row in result)))
    except Exception as err:
        print(json.dumps(dict(error=str(err))), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
