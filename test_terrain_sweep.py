import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from generator import Config, Grid, elevation, clean_terrain, write_terrain_svg
from terrain_sweep import generate_study, group_parameters


class TerrainSweepTests(unittest.TestCase):
    def test_increasing_spatial_variation(self):
        groups = [group_parameters(i) for i in range(1, 11)]
        self.assertEqual(groups[0], {'landmass_scale': .36, 'roughness': .1})
        self.assertAlmostEqual(groups[-1]['landmass_scale'], .045)
        self.assertAlmostEqual(groups[-1]['roughness'], .7)
        for a, b in zip(groups, groups[1:]):
            self.assertGreater(a['landmass_scale'], b['landmass_scale'])
            self.assertLess(a['roughness'], b['roughness'])
        with self.assertRaises(ValueError):
            group_parameters(0)
        with self.assertRaises(ValueError):
            group_parameters(1, smooth=.8, rough=.2)

    def test_fifty_terrain_only_exports_and_reproducibility(self):
        config = Config(hex_count=240, province_count=12, min_land_component=5, min_water_component=5)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('generator.partition', side_effect=AssertionError('Province division must not run')):
                manifest = generate_study(root, base=config, progress=lambda _: None)
            self.assertEqual(len(manifest['groups']), 10)
            self.assertEqual(len(list(root.rglob('*.svg'))), 50)
            self.assertFalse(list(root.rglob('03_provinces.svg')))
            for group in manifest['groups']:
                self.assertEqual(len(group['maps']), 5)
                self.assertEqual([m['seed'] for m in group['maps']], manifest['sample_seeds'])
                for sample in group['maps']:
                    self.assertIsNone(sample['classification'])
                    ET.parse(root / sample['path'] / '02_cleaned.svg')
            folder = root / manifest['groups'][3]['maps'][1]['path']
            saved = Config(**json.loads((folder / 'parameters.json').read_text()))
            grid = Grid(saved.hex_count, saved.aspect_ratio, saved.wrap_x)
            heights, terrain, sea = elevation(saved, grid)
            cleaned, _ = clean_terrain(terrain, grid, saved)
            write_terrain_svg(root / '02_cleaned.svg', grid, heights, cleaned, sea)
            self.assertEqual((folder / '02_cleaned.svg').read_bytes(), (root / '02_cleaned.svg').read_bytes())


if __name__ == '__main__':
    unittest.main()
