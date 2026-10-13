from dataclasses import replace
import unittest

from mapgen.app import parse_config
from mapgen.generator import Config
from mapgen.high_oceans import build_high_oceans
from mapgen.powers import assign_powers
from mapgen.profiles import targets_for
from mapgen.supply_centers import center_budget


def fixture(edges, water=(), centers=()):
    ids = sorted({n for edge in edges for n in edge})
    provinces = [{'id': p, 'terrain': 'water' if p in water else 'land',
                  'neighbors': sorted({b if a == p else a for a, b in edges if p in (a,b)}),
                  'supply_center': p in centers} for p in ids]
    return provinces, build_high_oceans(provinces)


class PowerTests(unittest.TestCase):
    def test_capacity_and_sc_budget_count_factor_once(self):
        ordinary = parse_config({'global_seed':42})
        asymmetric = parse_config({'global_seed':42, 'asymmetric':True})
        self.assertEqual((ordinary.province_count, asymmetric.province_count), (99,149))
        self.assertEqual((center_budget(ordinary)['count'],center_budget(asymmetric)['count']), (36,55))
        self.assertEqual(targets_for(Config(asymmetric=True))['province_count'],149)
        self.assertEqual(parse_config({'asymmetric':True,'size_ratio':1.2}) .province_count,178)
        self.assertEqual(parse_config({'asymmetric':True,'province_count':9999}).province_count,222)
        # Explicit counts are already final, including capacity; resolving is idempotent.
        self.assertEqual(center_budget(asymmetric), center_budget(asymmetric.resolved()))
        self.assertEqual(center_budget(replace(asymmetric,sc_richness=1.2))['count'],66)

    def test_separated_islands_form_fleet_group(self):
        p,m=fixture([(1,4),(2,4),(3,4),(4,5),(5,6),(6,7)],water={4,5},centers={1,2,3,6,7})
        r=assign_powers(p,m,Config(players=1))
        self.assertEqual(r['status'],'unavailable')  # majority would be met at the start
        # Add enough distant centers to avoid an instant victory.
        p,m=fixture([(1,4),(2,4),(3,4),(4,5),(5,6),(6,7),(7,8)],water={4,5},centers={1,2,3,6,7,8})
        r=assign_powers(p,m,Config(players=2))
        self.assertEqual(r['status'],'complete')
        self.assertEqual(r['victory_count'],4)
        fleet = next(x for x in r['players'] if x['starting_centers']==[1,2,3])
        self.assertTrue(all(w['unit_type']=='fleet' for w in fleet['two_step_routes'].values()))
        self.assertEqual(len({pid for power in r['players'] for pid in power['starting_centers']}),6)
        for province in p:
            if province['supply_center']:
                self.assertEqual(province['owner'],province['core'])
        self.assertEqual(r,assign_powers(p,m,Config(players=2)))
        for power in r['players']:
            self.assertTrue(power['coastal_starting_centers'])

    def test_inland_triple_rejected_even_with_enough_coastal_centers(self):
        # The inland triple is compact; coastal SCs are too far apart to form a group.
        edges = [(1,2),(2,3),(1,3),(3,4),(4,5),(5,6),(6,7),(7,8),(8,9),(9,10),
                 (10,11),(11,12),(12,13),(13,14),(14,15),(6,16),(10,16),(15,16)]
        # Separate seas prevent a fleet from linking the coastal centers in two moves.
        edges = [e for e in edges if 16 not in e] + [(6,16),(10,17),(15,18)]
        p,m=fixture(edges, water={16,17,18}, centers={1,2,3,6,10,15})
        result=assign_powers(p,m,Config(players=1))
        self.assertEqual(result['status'],'unavailable')
        self.assertIn('coastal-start',result['message'])
        self.assertTrue(all(x['owner'] is None for x in p))

    def test_coastal_quota_is_per_power_not_per_map(self):
        p,m=fixture([(1,2),(2,3),(3,4),(4,5),(5,6),(1,7)],water={7},centers=set(range(1,7)))
        result=assign_powers(p,m,Config(players=2))
        self.assertEqual(result['status'],'unavailable')
        self.assertIn('only 1 coastal SCs',result['message'])
        self.assertTrue(all(x['owner'] is None for x in p))

    def test_three_move_chain_is_not_a_valid_group(self):
        p,m=fixture([(n,n+1) for n in range(1,19)],centers={1,4,7,10,13,16,19})
        r=assign_powers(p,m,Config(players=2))
        self.assertEqual(r['status'],'unavailable')
        self.assertTrue(all(x['owner'] is None for x in p))

    def test_one_type_must_reach_both_destinations(self):
        # 1 reaches inland 2 by army, island 3 by fleet, but no single type reaches both.
        p,m=fixture([(1,2),(1,4),(4,3),(3,5),(5,6),(6,7),(7,8),(8,9)],water={4,5,7,8},centers={1,2,3,6,9})
        r=assign_powers(p,m,Config(players=2))
        self.assertEqual(r['status'],'unavailable')
        from mapgen.powers import movement_graphs, paths_from
        graphs=movement_graphs(p,m)
        self.assertIn('2',paths_from(graphs['army'],'1'))
        self.assertNotIn('3',paths_from(graphs['army'],'1'))
        self.assertIn('3',paths_from(graphs['fleet'],'1'))
        self.assertNotIn('2',paths_from(graphs['fleet'],'1'))

    def test_asymmetric_and_disabled_clear_old_ownership(self):
        p,m=fixture([(n,n+1) for n in range(1,8)],centers=set(range(1,9)))
        for province in p:
            province['owner']='old'
        r=assign_powers(p,m,Config(asymmetric=True))
        self.assertEqual(r['status'],'not_implemented')
        self.assertTrue(all(x['owner'] is None for x in p))
        self.assertEqual(assign_powers(p,m,Config(sc_enabled=False))['status'],'unavailable')
