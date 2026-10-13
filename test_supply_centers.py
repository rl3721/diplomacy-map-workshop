import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

from generator import Config, generate
from high_oceans import build_high_oceans
from supply_centers import designate, center_budget


class SupplyCenterTests(unittest.TestCase):
    def fixture(self):
        provinces = []
        for i in range(36):
            x, y = i % 6, i // 6
            neighbors = [ny*6+nx+1 for nx, ny in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]
                         if 0 <= nx < 6 and 0 <= ny < 6]
            provinces.append({'id': i+1, 'terrain': 'land', 'category': 'inland', 'neighbors': neighbors})
        return provinces, build_high_oceans(provinces)

    def test_budget_determinism_and_seed_variation(self):
        p, g = self.fixture()
        config = Config(players=2)
        a = designate(p, g, config)
        self.assertEqual(a['count'], 10)
        self.assertEqual(a['budget']['base_per_player'], 5.2)
        self.assertEqual(a, designate(p, g, config))
        self.assertNotEqual(a['province_ids'], designate(p, g, replace(config, sc_seed=43))['province_ids'])
        self.assertEqual(a['score'], max(a['candidate_scores']))
        self.assertAlmostEqual(a['score'], sum(a['components'][k]*v for k,v in a['weights'].items()))
        self.assertTrue(all(p['home_power'] is None and p['owner'] is None for p in p))

    def test_disabled_zero_infeasible_and_exclusions(self):
        p, g = self.fixture()
        p[0]['impassable'] = True
        p[1]['terrain'] = 'water'
        # Remove these from naval consideration for this artificial graph.
        g['locations'] = [loc for loc in g['locations'] if loc['name'] not in ('1','2')]
        for loc in g['locations']:
            loc['neighbors'] = [n for n in loc['neighbors'] if n not in ('1','2')]
        result = designate(p, g, Config(players=2))
        self.assertFalse({1,2} & set(result['province_ids']))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            designate(p, g, Config(players=100))
        result = designate(p, g, Config(players=100, sc_enabled=False))
        self.assertEqual(result['count'], 0)
        self.assertFalse(any(p['supply_center'] for p in p))
        self.assertEqual(designate(p,g,Config(sc_enabled=False))['count'],0)

    def test_islands_use_separate_land_regions_and_naval_access(self):
        p = [{'id': i, 'terrain': 'water' if i==5 else 'land',
              'category': 'sea' if i==5 else 'coastal', 'neighbors': ns}
             for i, ns in [(1,[2,5]),(2,[1,5]),(3,[4,5]),(4,[3,5]),(5,[1,2,3,4])]]
        r = designate(p,build_high_oceans(p),Config(players=1,province_count=5))
        self.assertEqual(len(r['regions']),2)
        self.assertEqual([r['actual_centers'] for r in r['regions']],[1,1])
        self.assertEqual(r['regions'][0]['naval_reachable_region_indices'],[1])

    def test_full_export_and_layout_independence(self):
        config = Config(hex_count=600, province_count=12, players=1,land_province_fraction=.65,
                        seed=0,division_seed=0,candidates=1)
        with tempfile.TemporaryDirectory() as root:
            outputs=[]
            for name, seed in [('a',1),('b',2)]:
                folder=Path(root)/name
                r=generate(replace(config,sc_seed=seed),folder,lambda _:None)
                data=json.loads((folder/'map.json').read_text())
                outputs.append(data)
                svg=ET.parse(folder/'03_provinces.svg').getroot()
                markers=svg.findall(".//{http://www.w3.org/2000/svg}g[@class='supply-center']")
                self.assertEqual({int(m.get('data-province')) for m in markers},set(r['supply_centers']['province_ids']))
                self.assertEqual(len(markers),4)
            for key in ('province_ids','elevations','cleaned_land','high_oceans','impassable'):
                self.assertEqual(outputs[0][key],outputs[1][key])

    def test_configuration_validation(self):
        for values in [{'sc_enabled':1},{'sc_iterations':2.5},{'sc_richness':0},
                       {'sc_distribution':1.1},{'sc_seed':'abc'},{'sc_iterations':0}]:
            with self.assertRaises(ValueError):
                Config(**values).validate()

    def test_distribution_and_coastal_controls_change_placement(self):
        p, g = self.fixture()
        near = designate(p,g,Config(players=2,sc_distribution=0))['province_ids']
        far = designate(p,g,Config(players=2,sc_distribution=1))['province_ids']
        def mean_nearest(ids):
            return sum(min(abs((a-1)%6-(b-1)%6)+abs((a-1)//6-(b-1)//6)
                           for b in ids if b != a) for a in ids)/len(ids)
        self.assertGreater(mean_nearest(far),mean_nearest(near))
        for province in p[:18]:
            province['category']='coastal'
        inland=designate(p,g,Config(players=2,sc_coastal_preference=0))
        coastal=designate(p,g,Config(players=2,sc_coastal_preference=2))
        self.assertGreater(coastal['actual_coastal_count'],inland['actual_coastal_count'])


class SupplyCenterBudgetTests(unittest.TestCase):
    def test_player_scaling_and_richness(self):
        for players, provinces, richness, expected in [(3, 0, 1, 16), (10, 0, 1, 52),
                                                       (10, 100, 1, 37), (7, 99, .8, 29),
                                                       (7, 120, 1, 44)]:
            with self.subTest(players=players, provinces=provinces, richness=richness):
                budget = center_budget(Config(players=players, province_count=provinces, sc_richness=richness))
                self.assertEqual(budget['count'], expected)
                self.assertEqual(budget['base_per_player'], 5.2)

    def test_half_up_rounding_and_single_final_round(self):
        # 5.2 * 5 * (55/52) = 27.5: a tie must round upwards.
        self.assertEqual(center_budget(Config(players=5, sc_richness=55/52))['count'], 28)
        self.assertEqual(center_budget(Config(players=5, sc_richness=55/52-.0001))['count'], 27)
        # Rounding 36.4 before applying 1.2 would incorrectly give 43.
        self.assertEqual(center_budget(Config(sc_richness=1.2))['count'], 44)

    def test_resolved_config_and_automatic_ratio_agree(self):
        config = Config(size_ratio=.5)
        budget = center_budget(config)
        # CLI automatic sizing rounds 7 * 14.1 * 0.5 to 49. The UI instead
        # supplies its clamped explicit count (minimum 50); use the actual count.
        self.assertEqual(budget['source_province_count'], 49)
        self.assertEqual(budget['base_province_count'], 99)
        self.assertEqual(budget['province_ratio'], 49/99)
        self.assertEqual(budget, center_budget(config.resolved()))

    def test_fixed_base_and_actual_province_ratio(self):
        self.assertEqual(center_budget(Config())['count'], 36)
        self.assertEqual(center_budget(Config(province_count=50))['count'], 18)
        self.assertEqual(center_budget(Config(province_count=148))['count'], 54)
        self.assertEqual(center_budget(Config(sc_richness=1.2))['count'], 44)
        # A manual count overrides a stale size_ratio value.
        budget = center_budget(Config(province_count=99, size_ratio=1.5))
        self.assertEqual(budget['province_ratio'], 1)
        self.assertEqual(budget['count'], 36)
        self.assertEqual(center_budget(Config(sc_enabled=False))['count'], 0)

    def test_legacy_settings_cannot_override_base(self):
        from app import parse_config
        config = parse_config({'sc_starting_per_player': 100, 'sc_neutral_per_player': 100}, random_seeds=False)
        self.assertEqual(center_budget(config)['count'], 36)
        with self.assertRaises(ValueError):
            parse_config({'sc_base_per_player': 100})
