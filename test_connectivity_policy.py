import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from generator import Config, generate, Grid, measure
from scoring import connectivity_policy, score_map


class ConnectivityPolicyTests(unittest.TestCase):
    def score(self, graph):
        provinces = [{'id': pid, 'neighbors': neighbors, 'category': 'sea', 'terrain': 'water',
                      'hex_count': 100, 'target_hex_count': 100} for pid, neighbors in graph.items()]
        return score_map(provinces, [1.] * len(provinces),
                         Config(sc_enabled=False, weight_degree=0, weight_composition=0, weight_global=0,
                                weight_shape=0, weight_size=100))

    def test_degree_one_is_illegal_even_with_connectivity_weight_zero(self):
        result = self.score({1: [2], 2: [1, 3], 3: [2]})
        self.assertEqual(result['weighted_total'], 100)
        self.assertEqual(result['total'], 0)
        self.assertFalse(result['valid'])
        self.assertEqual(result['connectivity_policy']['one_neighbor_province_ids'], [1, 3])

    def test_degree_two_is_legal_with_resolution_independent_penalty(self):
        triangle = {1: [2, 3], 2: [1, 3], 3: [1, 2]}
        doubled = dict(triangle)
        doubled.update({pid + 3: [nb + 3 for nb in ns] for pid, ns in triangle.items()})
        for graph in (triangle, doubled):
            result = self.score(graph)
            self.assertTrue(result['valid'])
            self.assertEqual(result['total'], 80)
            self.assertEqual(result['connectivity_policy']['penalty_points'], 20)
        result = self.score({1: [2, 3, 4], 2: [1, 3, 4], 3: [1, 2, 4], 4: [1, 2, 3]})
        self.assertEqual(result['total'], 100)

    def test_counts_distinct_neighbors_not_seam_pieces(self):
        result = connectivity_policy([{'id': 1, 'neighbors': [1, 2, 2]}])
        self.assertEqual(result['one_neighbor_province_ids'], [1])

    def test_illegal_measure_is_distinct_from_valid_geometry(self):
        result = measure([0, 1], [True, True], Grid(2, 1), [1, 1], Config(sc_enabled=False, province_count=2))
        self.assertTrue(result['structurally_valid'])
        self.assertFalse(result['valid'])
        self.assertEqual(result['scoring']['total'], 0)

    def test_all_illegal_candidates_do_not_export_a_map(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name in ('03_provinces.svg', 'report.json', 'map.json', 'index.html'):
                (path / name).write_text('previous stale output')
            with self.assertRaisesRegex(ValueError, 'No legal province layout'):
                generate(Config(sc_enabled=False, hex_count=60, province_count=2, land_fraction=1, candidates=3), path, lambda _: None)
            failure = json.loads((path / 'generation_failure.json').read_text())
            self.assertEqual(failure['candidate_scores'], [0, 0, 0])
            self.assertEqual(len(failure['rejected_candidates']), 3)
            self.assertTrue((path / '02_cleaned.svg').exists())
            for name in ('03_provinces.svg', 'report.json', 'map.json', 'index.html'):
                self.assertFalse((path / name).exists())

    def test_legal_zero_score_candidate_beats_illegal_zero(self):
        import generator
        original_measure = generator.measure
        call = 0
        def forced_measure(*args):
            nonlocal call
            result = original_measure(*args)
            result['scoring']['total'] = 0
            result['valid'] = call > 0
            result['scoring']['connectivity_policy']['one_neighbor_province_ids'] = [1] if call == 0 else []
            call += 1
            return result
        with tempfile.TemporaryDirectory() as folder, patch('generator.measure', side_effect=forced_measure):
            report = generate(Config(sc_enabled=False, hex_count=97, province_count=1, land_fraction=1, candidates=2), folder, lambda _: None)
            self.assertEqual(report['selected_candidate'], 1)
            self.assertEqual(len(report['rejected_candidates']), 1)


if __name__ == '__main__':
    unittest.main()
