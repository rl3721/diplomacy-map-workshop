import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from high_oceans import build_high_oceans
from generator import Grid, write_svg


def province(pid, terrain, neighbors):
    return {'id': pid, 'terrain': terrain, 'neighbors': neighbors}


class HighOceanTests(unittest.TestCase):
    def test_capacity_minimum_formula_and_rounding(self):
        for sources, exits, expected in [(2, 13, 2), (8, 13, 6), (8, 5, 3), (8, 4, 2)]:
            outer = list(range(sources + 1, sources + exits + 1))
            land = sources + exits + 1
            provinces = [province(i, 'water', [j for j in range(1, sources + 1) if j != i] + outer)
                         for i in range(1, sources + 1)]
            provinces += [province(i, 'water', list(range(1, sources + 1)) + [land]) for i in outer]
            provinces.append(province(land, 'land', outer))
            graph = build_high_oceans(provinces)
            self.assertEqual(graph['oceans'][0]['capacity'], expected)
            lookup = {p['name']: p for p in graph['locations']}
            slots = graph['oceans'][0]['slots']
            for slot in slots:
                self.assertEqual(set(lookup[slot]['neighbors']), (set(slots) - {slot}) | {str(i) for i in outer})
                for neighbor in lookup[slot]['neighbors']:
                    self.assertIn(slot, lookup[neighbor]['neighbors'])

    def test_zero_capacity_is_reported(self):
        graph = build_high_oceans([province(1, 'water', [2]), province(2, 'water', [1])])
        self.assertEqual(graph['zero_capacity_region_ids'], [1])

    def fixture(self):
        return [province(1, 'land', [2, 5]), province(2, 'water', [1, 3, 5]),
                province(3, 'water', [2, 4]), province(4, 'water', [3, 5]),
                province(5, 'water', [1, 2, 4])]

    def test_named_slots_share_exits_and_preserve_capacity(self):
        graph = build_high_oceans(self.fixture())
        self.assertEqual(graph['oceans'][0]['slots'], ['3.1'])
        self.assertEqual(graph['oceans'][0]['capacity'], 1)
        locations = {p['name']: p for p in graph['locations']}
        self.assertEqual(set(locations['3.1']['neighbors']), {'2', '5'})
        self.assertEqual(len(locations), 4)
        for name, location in locations.items():
            self.assertEqual(location['capacity'], 1)
            self.assertNotIn(name, location['neighbors'])
            for neighbor in location['neighbors']:
                self.assertIn(name, locations[neighbor]['neighbors'])
        self.assertFalse(graph['one_neighbor_region_ids'])

    def test_internal_clique_cannot_hide_geographical_dead_end(self):
        graph = build_high_oceans([province(1, 'land', [2]),
                                  province(2, 'water', [1, 3, 4]),
                                  province(3, 'water', [2, 4]),
                                  province(4, 'water', [2, 3])])
        self.assertIn(3, graph['one_neighbor_region_ids'])

    def test_single_deep_sea_does_not_merge(self):
        graph = build_high_oceans([province(1, 'land', [2]),
                                  province(2, 'water', [1, 3]), province(3, 'water', [2])])
        self.assertEqual(graph['oceans'], [])

    def test_svg_has_named_circles_and_shared_hidden_geometry(self):
        graph = build_high_oceans(self.fixture())
        grid = Grid(100, 1.5)
        owners = [min(4, i // 20) for i in range(100)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'map.svg'
            write_svg(path, 'Test', grid, owners, {i: '#abcdef' for i in range(5)}, True, graph)
            root = ET.parse(path).getroot()
        ns = {'s': 'http://www.w3.org/2000/svg'}
        slots = root.findall(".//s:g[@class='high-ocean-slot']", ns)
        self.assertEqual({s.get('data-location') for s in slots}, {'3.1'})
        self.assertTrue(all(s.find('s:circle', ns) is not None for s in slots))
        self.assertEqual(len({s.find('s:circle', ns).get('r') for s in slots}), 1)
        paths = root.findall(".//s:g[@id='sea-adjacencies']/s:path", ns)
        data = {p.get('data-location'): p.get('d') for p in paths}
        self.assertIn('3.1', data)
        self.assertIsNone(root.find(".//s:path[@id='region-3']", ns))


if __name__ == '__main__':
    unittest.main()
