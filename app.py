import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gpa import calculate
from portal import parse_portal_text


ROOT = Path(__file__).resolve().parent
STATIC = {'/folio.webp': ('folio.webp', 'image/webp'), '/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}


class Handler(BaseHTTPRequestHandler):
    timeout = 15

    def send_data(self, status, body, media):
        self.send_response(status)
        self.send_header('Content-Type', media)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value):
        self.send_data(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def do_GET(self):
        if self.path not in STATIC:
            self.send_json(404, {'error': '页面不存在。'})
            return
        filename, media = STATIC[self.path]
        self.send_data(200, (ROOT / filename).read_bytes(), f'{media}; charset=utf-8' if media.startswith('text/') else media)

    def do_POST(self):
        media = {'/api/portal/text': 'text/plain', '/api/calculate': 'application/json'}.get(self.path)
        if media is None:
            self.send_json(404, {'error': '接口不存在。'})
            return
        try:
            port = self.server.server_port
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'} | getattr(self.server, 'public_hosts', set())
            origin = self.headers.get('Origin')
            if self.headers.get('Host') not in hosts or (origin and origin not in {f'http://{host}' for host in hosts}):
                raise ValueError('请在本机浏览器打开本程序。')
            size = int(self.headers.get('Content-Length', '0'))
            if self.headers.get_content_type() != media or not 0 < size <= 1_000_000:
                raise ValueError('文件太大、为空，或格式不受支持。')
            data = self.rfile.read(size)
            if self.path == '/api/portal/text':
                self.send_json(200, parse_portal_text(data.decode('utf-8')))
            else:
                rows = json.loads(data)
                if not isinstance(rows, list) or len(rows) > 1000 or any(not isinstance(row, dict) for row in rows):
                    raise ValueError('课程数据格式不正确，最多可计算 1000 行。')
                self.send_json(200, calculate(rows))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {'error': '课程数据格式不正确。'})
        except ValueError as error:
            self.send_json(400, {'error': str(error)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='辽宁大学 GPA 计算器')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--public-host', action='append', default=[])
    args = parser.parse_args()
    with ThreadingHTTPServer((args.bind, args.port), Handler) as server:
        server.public_hosts = set(args.public_host)
        print(f'监听 {args.bind}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
