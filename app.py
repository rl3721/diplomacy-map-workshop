"""Local Map workshop UI. Run python app.py; no third-party packages required."""
import argparse
from dataclasses import asdict, fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
import webbrowser

from generator import Config, generate
from profiles import STYLES, targets_for
from scoring import connectivity_policy

ROOT = Path(__file__).resolve().parent
ARTIFACTS = {'01_elevation.svg', '02_cleaned.svg', '03_provinces.svg',
             'parameters.json', 'report.json', 'map.json', 'index.html'}

LOCKED_SETTINGS = {f.name: getattr(Config(), f.name) for f in fields(Config)
                   if f.name.startswith('weight_') or f.name.endswith('_tolerance')
                   or f.name in ('province_style', 'reference_profile')}


def province_limits(players, hex_count):
    base = targets_for(Config(players=players))['province_count']
    return base, min(hex_count, math.ceil(base * .5)), min(hex_count, math.floor(base * 1.5))


def parse_config(values, random_seeds=True):
    if not isinstance(values, dict):
        raise ValueError('Parameters must be a JSON object')
    unknown = set(values) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError('Unknown parameters: ' + ', '.join(sorted(unknown)))
    settings = dict(values)
    settings.update(LOCKED_SETTINGS)
    for name in ('seed', 'division_seed'):
        if settings.get(name) in (None, ''):
            settings[name] = secrets.randbelow(2 ** 31) if random_seeds else 42
    config = Config(**settings)
    # Migrate old absolute cleanup settings to fractions in the workshop.
    for kind in ('land', 'water'):
        absolute = getattr(config, f'min_{kind}_component')
        if type(absolute) is int and absolute >= 0 and type(config.hex_count) is int and config.hex_count > 0:
            setattr(config, f'min_{kind}_fraction', min(1., absolute / config.hex_count))
            setattr(config, f'min_{kind}_component', -1)
    if config.land_province_fraction == -1:
        config.land_province_fraction = .75
    if type(config.players) is int and 1 <= config.players <= 100 and type(config.hex_count) is int and config.hex_count > 0:
        if type(config.province_count) is not int:
            raise ValueError('province_count must be an integer')
        base, minimum, maximum = province_limits(config.players, config.hex_count)
        if isinstance(config.size_ratio, (int, float)) and not isinstance(config.size_ratio, bool) and .5 <= config.size_ratio <= 1.5:
            requested = config.province_count or round(base * config.size_ratio)
            config.province_count = max(minimum, min(maximum, requested))
    config.validate()
    return config


def result_summary(folder, job_id):
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    if not connectivity_policy(report['provinces'])['legal']:
        raise ValueError('Historical map contains a one-neighbor province; regenerate it under the current rule.')
    parameters = json.loads((folder / 'parameters.json').read_text(encoding='utf-8'))
    if report.get('high_oceans', {}).get('one_neighbor_region_ids'):
        raise ValueError('Map contains a one-neighbor merged region; regenerate it.')
    if not report.get('impassable', {}).get('legal', True):
        raise ValueError('Impassable placement invalidates movement connectivity; regenerate it.')
    return {'id': job_id, 'state': 'complete', 'message': 'Map ready', 'progress': 1,
            'parameters': parameters, 'province_count': report['province_count'],
            'impassable_count': report.get('impassable', {}).get('count', 0),
            'playable_location_count': report.get('playable_location_count', report['province_count']),
            'categories': report['scoring']['composition']['actual_counts'],
            'scoring': report['scoring'], 'elapsed_seconds': report['elapsed_seconds'],
            'degree': report['degree_statistics']['all'],
            'urls': {name: f'/runs/{job_id}/{name}' for name in ARTIFACTS}}


class Workshop:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = None
        self.token = secrets.token_urlsafe(32)

    def latest(self):
        folders = sorted((p for p in self.output.iterdir() if p.is_dir() and re.fullmatch(r'[a-f0-9]{16}', p.name)),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        for folder in folders:
            try:
                return result_summary(folder, folder.name)
            except (OSError, ValueError, KeyError):
                continue
        return None

    def start(self, config):
        with self.lock:
            if self.active is not None:
                raise RuntimeError('A map is already generating. Wait for it to finish.')
            job_id = secrets.token_hex(8)
            self.active = job_id
            self.jobs[job_id] = {'id': job_id, 'state': 'running', 'message': 'Starting map generation', 'progress': 0}
        threading.Thread(target=self.run, args=(job_id, config), daemon=True).start()
        return job_id

    def run(self, job_id, config):
        def progress(message):
            candidate = re.search(r'candidate (\d+)/(\d+)', message)
            fraction = (.15 + .75 * int(candidate[1]) / int(candidate[2]) if candidate else
                        .05 if message.startswith('1/') else .1 if message.startswith('2/') else
                        .95 if message.startswith('5/') else None)
            with self.lock:
                self.jobs[job_id]['message'] = message.replace('Province candidate', 'Iteration')
                if fraction is not None:
                    self.jobs[job_id]['progress'] = fraction
        try:
            folder = self.output / job_id
            generate(config, folder, progress)
            result = result_summary(folder, job_id)
            with self.lock:
                self.jobs[job_id] = result
                self.active = None
        except Exception as error:
            with self.lock:
                self.jobs[job_id].update(state='error', message=str(error), progress=0)
                self.active = None

    def job(self, job_id):
        with self.lock:
            return dict(self.jobs[job_id]) if job_id in self.jobs else None


def handler_for(workshop):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_bytes(self, content, content_type, status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def json_response(self, value, status=200):
            self.send_bytes(json.dumps(value).encode('utf-8'), 'application/json; charset=utf-8', status)

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.json_response({'error': 'Invalid host'}, 403)
            path = urlsplit(self.path).path
            if path == '/api/config':
                defaults = asdict(Config())
                defaults.update(seed=None, division_seed=None)
                return self.json_response({'defaults': defaults, 'presets': STYLES,
                                           'targets': targets_for(Config()), 'token': workshop.token,
                                           'province_bases': {p: province_limits(p, 500000)[0] for p in range(1, 101)}})
            if path == '/api/latest':
                return self.json_response(workshop.latest())
            if path.startswith('/api/jobs/'):
                job = workshop.job(path.rsplit('/', 1)[-1])
                return self.json_response(job or {'error': 'Unknown generation'}, 200 if job else 404)
            if path in ('/', '/index.html', '/style.css', '/ui.js'):
                name = 'index.html' if path == '/' else path[1:]
                mime = {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[name.rsplit('.', 1)[1]]
                return self.send_bytes((ROOT / 'ui' / name).read_bytes(), mime + '; charset=utf-8')
            match = re.fullmatch(r'/runs/([a-f0-9]{16})/([^/]+)', path)
            if match and match[2] in ARTIFACTS:
                file = workshop.output / match[1] / match[2]
                if file.is_file():
                    mime = 'image/svg+xml' if file.suffix == '.svg' else 'application/json' if file.suffix == '.json' else 'text/html'
                    return self.send_bytes(file.read_bytes(), mime + '; charset=utf-8')
            return self.json_response({'error': 'Not found'}, 404)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Workshop-Token') != workshop.token:
                return self.json_response({'error': 'Reload the application to reconnect.'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('Invalid request size')
                body = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path not in ('/api/targets', '/api/generate'):
                    return self.json_response({'error': 'Not found'}, 404)
                config = parse_config(body, random_seeds=path == '/api/generate')
                if path == '/api/targets':
                    return self.json_response(targets_for(config))
                job_id = workshop.start(config)
                return self.json_response({'id': job_id}, 202)
            except (ValueError, TypeError) as error:
                return self.json_response({'error': str(error)}, 400)
            except RuntimeError as error:
                return self.json_response({'error': str(error)}, 409)
    return Handler


def make_server(port=8765, output=None):
    workshop = Workshop(output or ROOT / 'output' / 'app-runs')
    return ThreadingHTTPServer(('127.0.0.1', port), handler_for(workshop)), workshop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'app-runs')
    args = parser.parse_args()
    try:
        server, _ = make_server(args.port, args.output)
    except OSError as error:
        parser.exit(2, f'Cannot start the local application: {error}. Try --port 8766.\n')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Map workshop: {url}\nMaps saved in {args.output.resolve()}\nPress Ctrl+C to stop.', flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
