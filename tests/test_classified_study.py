import json
from pathlib import Path
import unittest

from tools.classified_study import sample_configs
from mapgen.profiles import STYLES, TERRAIN_GROUPS, targets_for
from tools.terrain_sweep import group_parameters


class ClassifiedStudyTests(unittest.TestCase):
    def test_presets_match_selected_groups_exactly(self):
        for style, group in TERRAIN_GROUPS.items():
            expected = group_parameters(group)
            self.assertEqual(STYLES[style]['landmass_scale'], expected['landmass_scale'])
            self.assertEqual(STYLES[style]['roughness'], expected['roughness'])
            self.assertEqual(STYLES[style]['stretch'], (1.0, 1.0))
            self.assertEqual(STYLES[style]['land_fraction'], .4)

    def test_thirty_maps_with_same_province_targets_and_original_seeds(self):
        samples = sample_configs()
        self.assertEqual(len(samples), 30)
        selection = json.loads((Path(__file__).resolve().parents[1] / 'examples' / 'terrain_selection.json').read_text())
        for style, group in TERRAIN_GROUPS.items():
            rows = [row for row in samples if row[0] == style]
            self.assertEqual(len(rows), 10)
            original = [row['seed'] for row in selection['selected_examples'] if row['style'] == style]
            self.assertEqual([row[3].seed for row in rows[:5]], original)
        expected = targets_for(samples[0][3])
        for style, group, sample, config in samples:
            config.validate()
            self.assertEqual(config.province_count, 99)
            self.assertEqual((config.size_ratio, config.inland_ratio, config.connectivity_ratio), (1., 1., 1.))
            self.assertEqual(targets_for(config), expected)


if __name__ == '__main__':
    unittest.main()
