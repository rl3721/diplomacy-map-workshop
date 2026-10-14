import unittest

from tools.water_threshold_study import calibrate, fit_threshold, sample_quantile
from mapgen.water_names import kind_from_features


class WaterThresholdStudyTests(unittest.TestCase):
    def test_ties_not_split_to_fabricate_requested_rate(self):
        result = fit_threshold([1, 1, 1, 2, 3], .5)
        self.assertEqual(result['threshold'], 1)
        self.assertEqual(result['qualified'], 3)
        self.assertEqual(result['achieved'], .6)
        self.assertIsNone(fit_threshold([], .5))

    def test_empty_and_ineligible_maps_do_not_dilute_candidate_rate(self):
        rows = []
        for number, value in enumerate([1, 2, 3, 4], 1):
            rows.append(dict(map_number=number, high_ocean=False, mouth_count=2,
                             bank_count=2, wider_mouth_count=2, width_ratio=value))
        rows.append(dict(map_number=99, high_ocean=True))
        result = calibrate(rows)
        for preset in result['strait']:
            self.assertEqual(preset['eligible'], 4)
            self.assertEqual(preset['maps_with_eligible'], 4)
            self.assertEqual(preset['qualified'], sum(r['width_ratio'] <= preset['threshold'] for r in rows[:4]))
        self.assertTrue(all(p['threshold'] is None for p in result['gulf']))

    def test_exploratory_mode_does_not_change_default_classification(self):
        row = dict(high_ocean=False, mouth_count=2, bank_count=2, wider_mouth_count=0,
                   width_ratio=.5, coast_fraction=.5, mouth_depth_ratio=2)
        self.assertEqual(kind_from_features(row)[0], 'sea')
        self.assertEqual(kind_from_features(row,strait_require_wider=False)[0], 'strait')
        self.assertEqual(kind_from_features(row)[0], 'sea')
        self.assertEqual(sample_quantile([1,3],.25),1.5)


if __name__ == '__main__':
    unittest.main()
