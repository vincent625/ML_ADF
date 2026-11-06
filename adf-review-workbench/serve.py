"""Loopback review UI: reads prepared packets and checks drafts in memory only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from intake import validate_record

ROOT = Path(__file__).resolve().parent
MAX_REQUEST = 65536


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = 'ADFReview/1'

    def log_message(self, *_):
        pass

    def _trusted(self, check_origin=False):
        expected = '127.0.0.1:' + str(self.server.server_address[1])
        if self.headers.get('Host') != expected:
            return False
        origin = self.headers.get('Origin')
        if check_origin and origin and origin != 'http://' + expected:
            return False
        return True

    def _send(self, status, body, mime='application/json; charset=utf-8', download=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._trusted():
            self._send(403, {'error': 'Local host required'})
            return
        path = urlsplit(self.path).path
        if path in ('/', '/workbench.html'):
            self._send(200, (ROOT / 'workbench.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/api/data':
            self._send(200, (ROOT / 'results/workbench-data.json').read_bytes())
        elif path == '/download/timing-template':
            self._send(200, (ROOT / 'templates/time_observations.csv').read_bytes(),
                       'text/csv; charset=utf-8', 'time_observations.csv')
        elif path.startswith('/download/packet/'):
            key = path.rsplit('/', 1)[-1]
            data = json.loads((ROOT / 'results/workbench-data.json').read_text())
            allowed = {p['issue_key'] for p in data['packets']}
            if key not in allowed:
                self._send(404, {'error': 'Unknown packet'})
            else:
                packet = next(p for p in data['packets'] if p['issue_key'] == key)
                self._send(200, packet, download=key + '-evidence.json')
        else:
            self._send(404, {'error': 'Unknown route'})

    def do_POST(self):
        if not self._trusted(check_origin=True):
            self._send(403, {'error': 'Local origin required'})
            return
        if urlsplit(self.path).path != '/api/check':
            self._send(404, {'error': 'Unknown route'})
            return
        if self.headers.get('Transfer-Encoding'):
            self._send(400, {'error': 'Transfer encoding unsupported'})
            return
        if self.headers.get_content_type() != 'application/json':
            self._send(415, {'error': 'JSON required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                self._send(413, {'error': 'Draft must be between 1 and 65536 bytes'})
                return
            record = json.loads(self.rfile.read(length))
            if not isinstance(record, dict):
                raise ValueError('Expected a record object')
            self._send(200, validate_record(record))
        except (ValueError, UnicodeError, TypeError, KeyError):
            self._send(400, {'error': 'Invalid draft record'})


def make_server(port=8877):
    return ThreadingHTTPServer(('127.0.0.1', port), ReviewHandler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    server = make_server(args.port)
    print('Review workbench: http://127.0.0.1:' + str(server.server_address[1]), flush=True)
    server.serve_forever()
