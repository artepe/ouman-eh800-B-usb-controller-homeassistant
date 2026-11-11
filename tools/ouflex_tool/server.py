"""Loopback-only HTTP interface with same-origin and per-run capability protection."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets


def make_server(app, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, value, code=200, kind='application/json'):
            body = value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') == '127.0.0.1:%d' % self.server.server_port

        def do_GET(self):
            if not self.valid_host():
                return self.reply({'error':'Invalid Host'}, 403)
            if self.path == '/':
                return self.reply(Path(__file__).with_name('index.html').read_text().replace('__TOKEN__', token), kind='text/html')
            self.reply({'error':'Not found'}, 404)

        def do_POST(self):
            origin = 'http://127.0.0.1:%d' % self.server.server_port
            if (not self.valid_host() or self.headers.get('X-Ouflex-Token') != token
                    or self.headers.get('Origin', origin) != origin):
                return self.reply({'error':'Invalid origin/capability'}, 403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_000_000:
                    raise ValueError('Request size outside 1..2000000')
                data = json.loads(self.rfile.read(size))
                if self.path == '/api/state':
                    result = app.state()
                elif self.path == '/api/import':
                    result = app.import_map(data['text'], data.get('firmware','2.3.3'))
                elif self.path == '/api/read':
                    result = app.read(data['keys'])
                elif self.path == '/api/write':
                    if type(data.get('test')) is not bool:
                        raise ValueError('Explicit test boolean required')
                    result = app.write(data['key'], data['value'], disconnected=data.get('disconnected'), test=data['test'])
                elif self.path == '/api/audit':
                    result = app.audit()
                else:
                    return self.reply({'error':'Not found'},404)
                self.reply(result)
            except Exception as err:
                self.reply({'error':str(err)},400)

    server = HTTPServer(('127.0.0.1',port), Handler)
    server.timeout = 2
    return server


def serve(app, port):
    with make_server(app, port) as server:
        print('Open http://127.0.0.1:%d (controller data stays local)' % server.server_port, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
