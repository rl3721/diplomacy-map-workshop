import copy
import math
import unittest

from generator import CLASSIC, Config
from scoring import (classic_reference, combine_scores, compare_graph, graph_metrics,
                     score_map, wasserstein)


class ScoringTests(unittest.TestCase):
    def test_known_graphs(self):
        chain = graph_metrics({0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}})
        self.assertEqual(chain['articulation_count'], 2)
        self.assertEqual(chain['bridge_count'], 3)
        self.assertEqual(chain['path_hop_histogram'], {1: 6, 2: 4, 3: 2})
        cycle = graph_metrics({0: {1, 3}, 1: {0, 2}, 2: {1, 3}, 3: {0, 2}})
        self.assertEqual(cycle['articulation_count'], 0)
        self.assertEqual(cycle['bridge_count'], 0)
        disconnected = graph_metrics({0: {1}, 1: {0}, 2: {3}, 3: {2}})
        self.assertAlmostEqual(disconnected['unreachable_pair_fraction'], 2 / 3)
        self.assertEqual(disconnected['component_sizes'], [2, 2])

    def test_long_graph_avoids_recursion_and_samples_paths(self):
        graph = {i: {nb for nb in (i - 1, i + 1) if 0 <= nb < 1100} for i in range(1100)}
        result = graph_metrics(graph)
        self.assertEqual(result['articulation_count'], 1098)
        self.assertEqual(result['bridge_count'], 1099)
        self.assertEqual(result['path_source_count'], 128)
        self.assertFalse(result['paths_exact'])

    def test_distribution_distance_uses_proportions(self):
        self.assertEqual(wasserstein({3: 1, 5: 1}, {3: 100, 5: 100}), 0)
        self.assertEqual(wasserstein({3: 1}, {5: 1}), 2)

    def test_classic_reference_is_consistent_and_scores_perfectly(self):
        reference = classic_reference()
        provinces = copy.deepcopy(reference['provinces'])
        self.assertEqual(len(provinces), 75)
        lookup = {p['id']: p for p in provinces}
        for province in provinces:
            for neighbor in province['neighbors']:
                self.assertIn(province['id'], lookup[neighbor]['neighbors'])
            province.update(hex_count=100, target_hex_count=100)
        result = score_map(provinces, [1.0] * 75, Config(reference_profile='classic'))
        self.assertAlmostEqual(result['total'], 100)
        for part in result['components'].values():
            self.assertAlmostEqual(part['score'], 100)
        from collections import Counter
        for category, histogram in CLASSIC.items():
            self.assertEqual(Counter(len(p['neighbors']) for p in provinces if p['category'] == category), histogram)

    def test_travel_scaling_accepts_sqrt_growth(self):
        base = graph_metrics({0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}})
        larger = copy.deepcopy(base)
        larger['node_count'] = 16
        larger['component_sizes'] = [16]
        larger['path_hop_histogram'] = {2 * hops: count * 20 for hops, count in base['path_hop_histogram'].items()}
        comparison = compare_graph(larger, base, Config(reference_profile='classic'))
        self.assertAlmostEqual(comparison['path_score'], 100)
        self.assertAlmostEqual(comparison['fragmentation_score'], 100)
        unscaled = copy.deepcopy(base)
        unscaled['node_count'] = 16
        self.assertLess(compare_graph(unscaled, base, Config(reference_profile='classic'))['path_score'], 100)

    def test_weights_normalize_and_zero_disables(self):
        first = combine_scores({'degree': 25, 'size': 100}, {'degree': 40, 'size': 60})
        second = combine_scores({'degree': 25, 'size': 100}, {'degree': 4, 'size': 6})
        self.assertEqual(first['total'], second['total'])
        self.assertEqual(combine_scores({'degree': 25, 'size': 100}, {'degree': 0, 'size': 2})['total'], 100)

    def test_size_score_does_not_depend_on_hex_resolution(self):
        provinces = copy.deepcopy(classic_reference()['provinces'])
        for province in provinces:
            province.update(hex_count=110, target_hex_count=100)
        first = score_map(provinces, [.8] * 75, Config(reference_profile='classic'))
        for province in provinces:
            province['hex_count'] *= 100
            province['target_hex_count'] *= 100
        second = score_map(provinces, [.8] * 75, Config(reference_profile='classic'))
        self.assertEqual(first['components']['size']['score'], second['components']['size']['score'])

    def test_more_provinces_preserve_category_targets(self):
        reference = classic_reference()['provinces']
        doubled = []
        for suffix in ('a', 'b'):
            for province in reference:
                row = dict(province, id=province['id'] + suffix,
                           neighbors=[nb + suffix for nb in province['neighbors']],
                           hex_count=10, target_hex_count=10)
                doubled.append(row)
        result = score_map(doubled, [1.0] * 150, Config(reference_profile='classic'))
        self.assertAlmostEqual(result['components']['composition']['score'], 100)
        self.assertAlmostEqual(result['components']['degree']['score'], 100)
        for category, expected in {'inland': 28, 'coastal': 84, 'sea': 38}.items():
            self.assertAlmostEqual(result['composition']['expected_counts'][category], expected)
        # Two disconnected copies must not receive a perfect global score.
        self.assertLess(result['components']['global']['score'], 100)

    def test_invalid_scoring_options(self):
        for change in ({'weight_degree': -1}, {'path_tolerance': 0}, {'size_tolerance': math.inf},
                       {f'weight_{key}': 0 for key in ('degree', 'composition', 'global', 'size', 'shape')}):
            with self.assertRaises(ValueError):
                Config(**change).validate()

    def test_worst_shapes_are_not_hidden_by_average(self):
        provinces = copy.deepcopy(classic_reference()['provinces'])
        for province in provinces:
            province.update(hex_count=100, target_hex_count=100)
        result = score_map(provinces, [0.0] + [1.0] * 74, Config(reference_profile='classic'))
        shape = result['shape']
        self.assertGreater(shape['combined_shape_error'], shape['mean_shape_error'])
        self.assertIn(provinces[0]['id'], shape['worst_province_ids'])


if __name__ == '__main__':
    unittest.main()
