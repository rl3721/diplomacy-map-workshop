import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from mapgen.generator import Grid, write_svg
from mapgen.high_oceans import build_high_oceans
from mapgen.names import assign_names
from mapgen.sphere import SphereGrid


class ProvinceNamesTests(unittest.TestCase):
    def fixture(self):
        return [dict(id=i, terrain='land' if i in (1, 2, 6) else 'water',
                     hex_count=10, neighbors=[n for n in (i-1, i+1) if 1 <= n <= 6])
                for i in range(1, 7)]

    def test_landmass_prefix_uniqueness_and_reproducibility(self):
        provinces = self.fixture()
        graph = build_high_oceans(provinces)
        before = copy.deepcopy(graph)
        assign_names(provinces, graph, 42)
        names = [p['name'] for p in provinces]
        self.assertEqual(len(set(names)), 6)
        self.assertTrue(all(len(n) == 4 and n.isalpha() and n.isupper() for n in names))
        self.assertEqual(names[0][0], names[1][0])
        self.assertNotEqual(names[0][0], names[5][0])
        self.assertTrue(all(p['water_kind'] == 'sea' and p['name'].endswith('S') for p in provinces[2:5]))
        for old, new in zip(before['locations'], graph['locations']):
            self.assertEqual(old['name'], new['name'])
            self.assertEqual(old['neighbors'], new['neighbors'])
        assign_names(provinces, graph, 42)
        self.assertEqual(names, [p['name'] for p in provinces])
        assign_names(provinces, graph, 43)
        self.assertNotEqual(names, [p['name'] for p in provinces])

    def test_many_islands_and_collisions(self):
        provinces = [dict(id=i, terrain='land', hex_count=1, neighbors=[])
                     for i in range(1, 1001)]
        graph = build_high_oceans(provinces)
        result = assign_names(provinces, graph, 1)
        self.assertTrue(result['prefix_reuse'])
        self.assertEqual(len({p['name'] for p in provinces}), len(provinces))

    def test_high_ocean_display_slots_share_code_and_resolve_neighbors(self):
        provinces = self.fixture()
        provinces[4]['terrain'] = 'water'
        # Extend deep water to merge provinces 3 and 4.
        provinces[1]['terrain'] = 'water'
        graph = build_high_oceans(provinces)
        assign_names(provinces, graph, 42)
        self.assertTrue(graph['oceans'])
        for ocean in graph['oceans']:
            self.assertEqual(len(ocean['display_name']), 4)
            slots = [p for p in graph['locations'] if p['region_id'] == ocean['id']]
            self.assertTrue(all(p['display_name'].startswith(ocean['display_name'] + '.') for p in slots))
        lookup = {p['name']: p['display_name'] for p in graph['locations']}
        for location in graph['locations']:
            self.assertEqual(location['neighbor_display_names'], [lookup[n] for n in location['neighbors']])

    def test_sc_marker_radii_uniform_across_provinces_and_views(self):
        ns = {'s': 'http://www.w3.org/2000/svg'}
        for grid in (Grid(96, 1.6, False), Grid(96, 1.6, True), SphereGrid(97)):
            # Deliberately unequal regions and projected fragments.
            labels = [0 if i < 20 else 1 for i in range(grid.count)]
            with tempfile.TemporaryDirectory() as folder:
                radii = []
                for owners in ({}, {1: 'P1', 2: 'P100'}):
                    path = Path(folder) / 'map.svg'
                    write_svg(path, 'Markers', grid, labels, {0:'#aca', 1:'#aac'}, True,
                              supply_center_ids=[1, 2], power_owners=owners,
                              province_names={1:'ABCD', 2:'AEFG'})
                    groups = ET.parse(path).findall('.//s:g[@class="supply-center"]', ns)
                    self.assertGreaterEqual(len(groups), 2)
                    radii.extend(float(g.find('s:circle', ns).attrib['r']) for g in groups)
                self.assertGreater(min(radii), 0)
                self.assertEqual(len(set(radii)), 1)

    def test_core_marker_fill_and_neutral_marker(self):
        grid = Grid(96, 1.6)
        labels = [0 if i < 48 else 1 for i in range(grid.count)]
        ns = {'s': 'http://www.w3.org/2000/svg'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'map.svg'
            write_svg(path, 'Core markers', grid, labels, {0:'#aca',1:'#aac'}, True,
                      supply_center_ids=[1,2], power_owners={1:'P1'},
                      core_colors={1:'hsl(137,60%,70%)'})
            groups = ET.parse(path).findall('.//s:g[@class="supply-center"]', ns)
            fills = {int(g.attrib['data-province']): g.find('s:circle', ns).attrib['fill'] for g in groups}
            self.assertEqual(fills, {1:'hsl(137,60%,70%)', 2:'white'})
            self.assertTrue(all(len(g.findall('s:circle',ns)) == 1 for g in groups))
