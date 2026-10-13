import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mapgen import browser_api
from tools.build_site import build, PYTHON_FILES


class BrowserApiTests(unittest.TestCase):
    def test_static_build_has_relative_assets_and_only_runtime_files(self):
        with tempfile.TemporaryDirectory() as directory:
            site = build(directory)
            html = (site / 'index.html').read_text(encoding='utf-8')
            self.assertIn('src="./browser.js"', html)
            self.assertIn('href="./style.css"', html)
            self.assertNotIn('src="/ui.js"', html)
            self.assertTrue((site / '.nojekyll').is_file())
            self.assertEqual(json.loads((site / 'python/manifest.json').read_text()), PYTHON_FILES)
            self.assertFalse((site / 'python/mapgen/app.py').exists())
            self.assertTrue((site / 'python/mapgen/__init__.py').is_file())
            self.assertTrue(all((site / 'python' / name).is_file() for name in PYTHON_FILES))

    def test_browser_generation_rerun_failure_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(browser_api, 'OUTPUT', Path(directory)):
            settings = {'global_seed':0, 'players':1, 'province_count':12,
                        'hex_count':600, 'land_province_fraction':.65,
                        'min_land_component':12, 'min_water_component':12}
            messages = []
            first = browser_api.dispatch('/api/generate', settings, 'a'*16, messages.append)
            self.assertTrue(messages)
            first_map = json.loads(first['files']['map.json'])
            self.assertIn('<svg', first['files']['04_powers.svg'])
            with patch('mapgen.browser_api.generate', side_effect=ValueError('Test failure')):
                with self.assertRaises(ValueError):
                    browser_api.dispatch('/api/generate', settings, 'b'*16)
            self.assertTrue((Path(directory)/('a'*16)/'map.json').exists())
            second = browser_api.dispatch('/api/rerun', {'source_id':'a'*16, 'stage':'power', 'parameters':{}}, 'c'*16)
            second_map = json.loads(second['files']['map.json'])
            self.assertEqual(first_map['supply_centers'], second_map['supply_centers'])
            self.assertEqual(first_map['province_ids'], second_map['province_ids'])
            self.assertNotEqual(first_map['pipeline']['stage_seeds']['power'], second_map['pipeline']['stage_seeds']['power'])
            self.assertFalse((Path(directory)/('a'*16)).exists())
            self.assertEqual(len(list(Path(directory).iterdir())), 1)
            with self.assertRaises(ValueError):
                browser_api.dispatch('/api/generate', settings, '../escape')

    def test_browser_configuration_and_targets_share_local_rules(self):
        self.assertEqual(browser_api.dispatch('/api/config')['defaults']['players'], 7)
        target = browser_api.dispatch('/api/targets', {'asymmetric':True})
        self.assertEqual(target['province_count'],149)
        self.assertEqual(target['supply_center_budget']['count'],55)
