import json
from pathlib import Path
import random
import tempfile
import unittest
import xml.etree.ElementTree as ET

from generator import Config, Grid, allocate, clean_terrain, components, generate, outline_paths, size_targets


class GeneratorTests(unittest.TestCase):
    def test_grid_geometry_matches_adjacency(self):
        grid = Grid(97, 1.5)
        for cell, neighbors in enumerate(grid.neighbors):
            vertices = set(grid.vertices(cell))
            for nb in neighbors:
                self.assertIn(cell, grid.neighbors[nb])
                self.assertEqual(len(vertices & set(grid.vertices(nb))), 2)

    def test_cleanup_and_idempotence(self):
        grid = Grid(100, 1)
        terrain = [False] * 100
        terrain[45] = True
        config = Config(sc_enabled=False, hex_count=100, min_land_component=2, min_water_component=2)
        cleaned, _ = clean_terrain(terrain, grid, config)
        self.assertFalse(any(cleaned))
        self.assertEqual(clean_terrain(cleaned, grid, config)[0], cleaned)
        self.assertEqual(terrain[45], True)

    def test_allocation_and_targets(self):
        self.assertEqual(sum(allocate([list(range(20)), list(range(80))], 10)), 10)
        with self.assertRaises(ValueError):
            allocate([[0], [1]], 1)
        targets = size_targets(50000, 75, .7, random.Random(1))
        self.assertEqual(sum(targets), 50000)
        self.assertGreaterEqual(min(targets), 1)

    def test_end_to_end_reproducibility_and_svg(self):
        config = Config(sc_enabled=False, hex_count=600, province_count=12, min_land_component=12,
                        min_water_component=12, land_province_fraction=.65, seed=0)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = generate(config, first, lambda _: None)
            generate(config, second, lambda _: None)
            self.assertEqual(result['province_count'], 12)
            data = json.loads((Path(first) / 'map.json').read_text())
            self.assertEqual(len(data['province_ids']), 600)
            grid = Grid(600, config.aspect_ratio)
            self.assertEqual(len(components(data['province_ids'], grid)), 12)
            self.assertEqual(sum(p['hex_count'] for p in data['provinces']), 600)
            for name in ('01_elevation.svg', '02_cleaned.svg', '03_provinces.svg', 'map.json'):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
                if name.endswith('.svg'):
                    ET.parse(Path(first) / name)

    def test_pure_terrain_and_single_hex(self):
        for fraction in (0, 1):
            with tempfile.TemporaryDirectory() as folder:
                report = generate(Config(sc_enabled=False, hex_count=1, province_count=1, land_fraction=fraction), folder, lambda _: None)
                self.assertTrue(report['valid'])
                self.assertEqual(report['degree_statistics']['all']['mean'], 0)

    def test_boundary_cancellation(self):
        grid = Grid(2, 5)
        paths = outline_paths(grid, [0, 0])
        self.assertEqual(paths[0].count(' L'), 9)  # Ten outside edges, shared edge removed.

    def test_outline_holes_preserve_area(self):
        import re
        grid = Grid(100, 1)
        labels = [0] * 100
        labels[45] = 1
        for label, path in outline_paths(grid, labels).items():
            area = 0
            for loop in path.split(' Z'):
                points = [tuple(map(int, pair)) for pair in re.findall(r'(-?\d+),(-?\d+)', loop)]
                if points:
                    area += sum(a[0] * b[1] - b[0] * a[1]
                                for a, b in zip(points, points[1:] + points[:1])) / 2
            self.assertEqual(area, labels.count(label) * 6)

    def test_infeasible_run_keeps_intermediates_without_stale_final(self):
        with tempfile.TemporaryDirectory() as folder:
            final = Path(folder) / '03_provinces.svg'
            final.write_text('old map')
            config = Config(sc_enabled=False, hex_count=600, province_count=1, min_land_component=12,
                            min_water_component=12)
            with self.assertRaises(ValueError):
                generate(config, folder, lambda _: None)
            self.assertTrue((Path(folder) / '01_elevation.svg').exists())
            self.assertTrue((Path(folder) / '02_cleaned.svg').exists())
            self.assertFalse(final.exists())

    def test_bad_parameters(self):
        for changes in ({'hex_count': 0}, {'roughness': 2}, {'province_count': 50001},
                        {'aspect_ratio': float('nan')}, {'hex_count': 2.5}):
            with self.assertRaises(ValueError):
                Config(sc_enabled=False, **changes).validate()


if __name__ == '__main__':
    unittest.main()
