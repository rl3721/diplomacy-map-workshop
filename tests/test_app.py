import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mapgen.app import make_server, parse_config, Workshop
from mapgen.generator import Config


class AppTests(unittest.TestCase):
    def test_workshop_defaults_locked_settings_and_count_limits(self):
        c = parse_config({})
        self.assertEqual((c.terrain_style, c.hex_count, c.land_province_fraction), ('peninsula', 5000, .75))
        self.assertEqual(c.cleanup_thresholds(), {'min_land_component': 180, 'min_water_component': 180})
        locked = parse_config({'province_style': 'islands', 'reference_profile': 'world',
                               'weight_degree': 999, 'shape_tolerance': 99})
        self.assertEqual((locked.province_style, locked.reference_profile), ('auto', 'auto'))
        self.assertEqual((locked.weight_degree, locked.shape_tolerance), (40., .6))
        self.assertEqual(parse_config({'province_count': 9999}).province_count, 148)
        self.assertEqual(parse_config({'province_count': 1}).province_count, 50)
        self.assertEqual(parse_config({'size_ratio': .5}).province_count, 50)
        self.assertEqual(parse_config({'size_ratio': 1.5}).province_count, 148)
        self.assertEqual(parse_config({'hex_count': 50000}).cleanup_thresholds()['min_land_component'], 1800)
        old = parse_config({'hex_count': 50000, 'min_land_component': 180})
        self.assertAlmostEqual(old.min_land_fraction, .0036)
        self.assertEqual(old.min_land_component, -1)

    def test_optional_and_fixed_seeds(self):
        with patch('mapgen.app.secrets.randbelow', return_value=123):
            config = parse_config({'global_seed': ''})
        self.assertEqual(config.global_seed, 123)
        self.assertEqual(config, parse_config({'global_seed': 123}))
        self.assertEqual(len({config.seed, config.division_seed, config.sc_seed}), 3)
        config = parse_config({'global_seed': 0, 'seed': 999, 'division_seed': -10})
        self.assertEqual(config.global_seed, 0)
        self.assertNotEqual(config.seed, 999)
        for values in ({'bad': 1}, {'size_ratio': 2}, {'seed': 'word'}, ['not an object']):
            with self.assertRaises(ValueError):
                parse_config(values)

    def test_random_global_seed_clears_saved_stage_overrides(self):
        saved = {'global_seed': 42, 'terrain_seed_override': 1,
                 'province_seed_override': 2, 'sc_seed_override': 3}
        replay = parse_config(saved)
        self.assertEqual((replay.seed, replay.division_seed, replay.sc_seed), (1, 2, 3))
        with patch('mapgen.app.secrets.randbelow', return_value=123):
            fresh = parse_config(dict(saved, global_seed=''))
        self.assertEqual(fresh, parse_config({'global_seed': 123}))

    def test_job_failure_releases_busy_state(self):
        with tempfile.TemporaryDirectory() as directory:
            workshop = Workshop(directory)
            workshop.jobs['test'] = {'id': 'test', 'state': 'running'}
            workshop.active = 'test'
            with self.assertRaises(RuntimeError):
                workshop.start(Config())
            with patch('mapgen.app.generate', side_effect=ValueError('Infeasible terrain')):
                workshop.run('test', Config())
            self.assertEqual(workshop.job('test')['state'], 'error')
            self.assertIsNone(workshop.active)

    def test_http_generation_validation_and_artifact_access(self):
        with tempfile.TemporaryDirectory() as directory:
            server, workshop = make_server(0, directory)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f'http://127.0.0.1:{server.server_port}'

            def get(path):
                with urlopen(base + path, timeout=15) as response:
                    return response.read()

            def post(path, data, token=None):
                request = Request(base + path, data=json.dumps(data).encode(),
                                  headers={'Content-Type': 'application/json', 'X-Workshop-Token': token or workshop.token})
                with urlopen(request, timeout=15) as response:
                    return json.load(response)

            try:
                self.assertIn(b'Diplomacy Map Workshop', get('/'))
                defaults = json.loads(get('/api/config'))
                self.assertIsNone(defaults['defaults']['global_seed'])
                self.assertEqual(post('/api/targets', {})['province_count'], 99)
                self.assertEqual(post('/api/targets', {})['supply_center_budget']['count'], 36)
                self.assertNotIn('sc_starting_per_player', defaults['defaults'])
                self.assertNotIn('sc_neutral_per_player', defaults['defaults'])
                self.assertEqual(post('/api/targets', {'province_count': 148})['supply_center_budget']['count'], 54)
                self.assertEqual(post('/api/targets', {'province_count': 99, 'size_ratio': 1.5})['supply_center_budget']['count'], 36)
                self.assertEqual(post('/api/targets', {'sc_starting_per_player': 100})['supply_center_budget']['count'], 36)
                with self.assertRaises(HTTPError) as error:
                    post('/api/targets', {'sc_base_per_player': 100})
                self.assertEqual(error.exception.code, 400)
                for path in ('/runs/../../profiles.py', '/profiles.py'):
                    with self.assertRaises(HTTPError) as error:
                        get(path)
                    self.assertEqual(error.exception.code, 404)
                with self.assertRaises(HTTPError) as error:
                    post('/api/generate', {}, 'wrong-token')
                self.assertEqual(error.exception.code, 403)
                with self.assertRaises(HTTPError) as error:
                    post('/api/generate', {'connectivity_ratio': 5})
                self.assertEqual(error.exception.code, 400)
                values = {'hex_count': 600, 'players': 1, 'province_count': 12, 'candidates': 12,
                          'seed': 0, 'division_seed': 42, 'land_province_fraction': .65, 'min_land_component': 12, 'min_water_component': 12}
                result = post('/api/generate', values)
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    job = json.loads(get('/api/jobs/' + result['id']))
                    if job['state'] != 'running':
                        break
                    time.sleep(.05)
                self.assertEqual(job['state'], 'complete', job)
                self.assertEqual(job['province_count'], 12)
                self.assertEqual(job['supply_centers']['count'], 4)
                map_data = json.loads(get(job['urls']['map.json']))
                self.assertEqual(map_data['supply_centers']['budget']['base_per_player'], 5.2)
                self.assertEqual(sum(p['supply_center'] for p in map_data['provinces']), 4)
                self.assertIn(b'<svg', get(job['urls']['03_provinces.svg']))
                self.assertEqual(json.loads(get('/api/latest'))['id'], job['id'])
                self.assertEqual(json.loads(get(job['urls']['parameters.json']))['global_seed'], 0)
                self.assertEqual(len(list(Path(directory).iterdir())), 1)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
