import unittest
from mapgen.high_oceans import build_high_oceans
from mapgen.impassable import apply_impassable
from mapgen.generator import Config


class ImpassableTests(unittest.TestCase):
    def fixture(self, count=50):
        provinces = [{'id': i+1, 'terrain': 'land', 'neighbors': [j+1 for j in range(count) if j != i]}
                     for i in range(count)]
        return provinces, list(range(count)), [i / count for i in range(count)]

    def test_highest_mean_and_graph_removal(self):
        provinces, owners, heights = self.fixture()
        owners.append(0)
        heights[0] = 1
        heights.append(0)
        graph = build_high_oceans(provinces)
        result = apply_impassable(provinces, owners, heights, graph)
        self.assertEqual(result['province_ids'], [50])
        self.assertTrue(result['legal'])
        self.assertEqual(len(graph['locations']), 49)
        self.assertTrue(all('50' not in p['neighbors'] for p in graph['locations']))
        self.assertTrue(provinces[-1]['impassable'])

    def test_floor_disabled_zero_and_ties(self):
        for count, enabled, ratio, expected in [(49, True, .02, 0), (100, True, .02, 2),
                                                (50, False, .5, 0), (50, True, 0, 0)]:
            provinces, owners, heights = self.fixture(count)
            result = apply_impassable(provinces, owners, [.5]*count, build_high_oceans(provinces), enabled, ratio)
            self.assertEqual(result['province_ids'], list(range(1, expected+1)))

    def test_blocking_bridge_is_illegal(self):
        edges = [[2, 3], [1, 3], [1, 2, 4], [3, 5, 6], [4, 6], [4, 5]]
        provinces = [{'id': i+1, 'terrain': 'land', 'neighbors': n} for i, n in enumerate(edges)]
        result = apply_impassable(provinces, list(range(6)), [0, 0, 1, 0, 0, 0], build_high_oceans(provinces), ratio=.2)
        self.assertFalse(result['legal'])
        self.assertTrue(result['unreachable_region_ids'])

    def test_validation(self):
        for kwargs in [{'impassable_ratio': -.1}, {'impassable_ratio': 1.1}, {'impassable_enabled': 1}]:
            with self.assertRaises(ValueError):
                Config(**kwargs).validate()
