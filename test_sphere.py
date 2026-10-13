import json
import math
from collections import deque
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from generator import Config, clean_terrain, components, elevation, generate
from profiles import targets_for
from sphere import SphereGrid


class SphereTests(unittest.TestCase):
    def test_closed_surface_and_real_boundary_adjacency(self):
        for count in (12, 97, 1200):
            g = SphereGrid(count)
            width, height = round(g.display_width, 9), round(g.display_height, 9)
            def vertex(p):
                x, y = p
                return (0 if y in (0, height) or x == width else x, y)
            edges = {}
            vertices = set()
            for cell, segments in enumerate(g.render_edges):
                for a, b in segments:
                    a, b = vertex(a), vertex(b)
                    if a == b:  # projection's pole edges have zero physical length
                        continue
                    key = tuple(sorted((a, b)))
                    vertices.update((a, b))
                    edges.setdefault(key, []).append(cell)
            self.assertTrue(all(len(owners) == 2 for owners in edges.values()))
            # The rectangular cut can run through a cell; that is not a physical edge.
            edges = {edge: owners for edge, owners in edges.items() if owners[0] != owners[1]}
            vertices = {vertex for edge in edges for vertex in edge}
            self.assertEqual(len(vertices) - len(edges) + count, 2)  # sphere, not cylinder/torus
            expected = [set() for _ in range(count)]
            for a, b in edges.values():
                expected[a].add(b)
                expected[b].add(a)
            self.assertEqual([set(n) for n in g.neighbors], expected)
            self.assertEqual(len(components([0] * count, g)), 1)
            for a, ns in enumerate(g.neighbors):
                self.assertNotIn(a, ns)
                for b in ns:
                    self.assertAlmostEqual(g.edge_lengths[a][b], g.edge_lengths[b][a])
                    self.assertGreater(g.edge_lengths[a][b], 0)

    def test_equal_area_exact_count_and_display_independence(self):
        a, b = SphereGrid(50003, 1), SphereGrid(50003, 2)
        self.assertEqual(sum(a.row_sizes), 50003)
        self.assertEqual(a.neighbors, b.neighbors)
        self.assertEqual(a.xyz, b.xyz)
        for n, north, south in zip(a.row_sizes, a.latitude_bounds, a.latitude_bounds[1:]):
            self.assertAlmostEqual(2 * math.pi * (math.sin(north) - math.sin(south)) / n, a.area_per_cell)
        self.assertLess(a.row_sizes[0], max(a.row_sizes) / 10)

    def test_polar_routes_without_polar_hub_or_north_south_wrap(self):
        g = SphereGrid(4000)
        def hops(a, b):
            queue = deque([(a, 0)])
            seen = {a}
            while queue:
                cell, distance = queue.popleft()
                if cell == b:
                    return distance
                for nb in g.neighbors[cell]:
                    if nb not in seen:
                        seen.add(nb)
                        queue.append((nb, distance + 1))
        polar = hops(0, g.row_sizes[0] // 2)
        row = len(g.row_sizes) // 2
        equator = g.row_starts[row]
        self.assertLess(polar, hops(equator, equator + g.row_sizes[row] // 2))
        self.assertLess(g.distance2(0, g.row_sizes[0] // 2), g.distance2(equator, equator + g.row_sizes[row] // 2))
        self.assertTrue(set(g.neighbors[0]).isdisjoint(range(g.row_starts[-1], g.count)))
        self.assertLess(max(map(len, g.neighbors)), 12)

    def test_elevation_uses_sphere_positions_not_projected_coordinates(self):
        config = Config(sc_enabled=False, topology='sphere', hex_count=600, province_count=12)
        a, b = SphereGrid(600, .5), SphereGrid(600, 3)
        self.assertEqual(elevation(config, a), elevation(config, b))
        # Both sides of the display seam denote the same 3D location.
        b.xyz[1] = b.xyz[0]
        heights, _, _ = elevation(config, b)
        self.assertEqual(heights[0], heights[1])

    def test_cleanup_joins_across_seam(self):
        g = SphereGrid(600)
        row = 4  # non-offset row has an actual edge at the display seam
        a = g.row_starts[row]
        b = a + g.row_sizes[row] - 1
        terrain = [False] * g.count
        terrain[a] = terrain[b] = True
        cleaned, _ = clean_terrain(terrain, g, Config(sc_enabled=False, min_land_component=2, min_water_component=2))
        self.assertEqual(cleaned, terrain)

    def test_generate_and_reproduce_all_exports(self):
        config = Config(sc_enabled=False, topology='sphere', hex_count=1200, province_count=20, candidates=2,
                        min_land_component=15, min_water_component=15)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            report = generate(config, first, lambda _: None)
            generate(config, second, lambda _: None)
            g = SphereGrid(1200)
            data = json.loads((Path(first) / 'map.json').read_text())
            self.assertEqual(len(components(data['province_ids'], g)), 20)
            self.assertEqual(sum(p['hex_count'] for p in data['provinces']), 1200)
            self.assertAlmostEqual(sum(p['surface_area_steradians'] for p in data['provinces']), 4 * math.pi)
            self.assertEqual(data['grid']['cell_neighbors'], g.neighbors)
            self.assertEqual(report['grid']['topology'], 'sphere')
            for province in data['provinces']:
                cells = [i for i, pid in enumerate(data['province_ids']) if pid == province['id']]
                self.assertEqual(len({data['cleaned_land'][i] for i in cells}), 1)
                actual = {data['province_ids'][nb] for i in cells for nb in g.neighbors[i]} - {province['id']}
                self.assertEqual(actual, set(province['neighbors']))
            for name in ('01_elevation.svg', '02_cleaned.svg', '03_provinces.svg', 'map.json'):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
                if name.endswith('.svg'):
                    ET.parse(Path(first) / name)

    def test_single_province_has_no_phantom_polar_perimeter(self):
        with tempfile.TemporaryDirectory() as folder:
            report = generate(Config(sc_enabled=False, topology='sphere', hex_count=97, province_count=1,
                                     land_fraction=1, candidates=1), folder, lambda _: None)
            province = report['provinces'][0]
            self.assertEqual(province['surface_perimeter_radians'], 0)
            self.assertEqual(province['perimeter_efficiency'], 1)

    def test_legacy_wrap_and_explicit_topology_precedence(self):
        self.assertEqual(Config(sc_enabled=False, wrap_x=True).resolved().topology, 'cylinder')
        self.assertFalse(Config(sc_enabled=False, topology='flat', wrap_x=True).resolved().wrap_x)
        self.assertTrue(Config(sc_enabled=False, topology='sphere').resolved().wrap_x)
        flat, sphere = targets_for(Config(sc_enabled=False, )), targets_for(Config(sc_enabled=False, topology='sphere'))
        for key in ('province_count', 'category_fractions', 'degree_histograms'):
            self.assertEqual(flat[key], sphere[key])
        self.assertEqual(sphere['global_profile'], 'world')
        for config in (Config(sc_enabled=False, topology='torus'), Config(sc_enabled=False, topology='sphere', hex_count=11, province_count=1)):
            with self.assertRaises(ValueError):
                config.validate()


if __name__ == '__main__':
    unittest.main()
