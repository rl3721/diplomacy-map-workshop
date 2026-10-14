from types import SimpleNamespace
import unittest

from mapgen.water_names import classify_water, kind_from_features
from mapgen.names import assign_names
from mapgen.high_oceans import build_high_oceans


def raster(width, height, water, candidate, factor=1):
    w, h = width * factor, height * factor
    neighbors = []
    land, owners = [], []
    for y in range(h):
        for x in range(w):
            point = x // factor, y // factor
            land.append(point not in water)
            owners.append(0 if point in candidate else 1 if point in water else 2)
            neighbors.append([ny*w+nx for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
                              if 0 <= nx < w and 0 <= ny < h])
    return SimpleNamespace(count=w*h, neighbors=neighbors), land, owners


class WaterClassificationTests(unittest.TestCase):
    def test_selected_threshold_boundaries(self):
        strait = dict(high_ocean=False, mouth_count=2, bank_count=2, wider_mouth_count=0,
                      coast_fraction=.5, width_ratio=1.0421002114378124, mouth_depth_ratio=5)
        self.assertEqual(kind_from_features(strait)[0], 'strait')
        self.assertEqual(kind_from_features(dict(strait,width_ratio=1.0422))[0], 'sea')
        gulf = dict(high_ocean=False, mouth_count=1, bank_count=1, wider_mouth_count=1,
                    coast_fraction=.7, width_ratio=2, mouth_depth_ratio=8.25)
        self.assertEqual(kind_from_features(gulf)[0], 'gulf')
        self.assertEqual(kind_from_features(dict(gulf,mouth_depth_ratio=8.251))[0], 'sea')

    def classify(self, water, candidate, factor=1):
        grid, land, owners = raster(31, 31, water, candidate, factor)
        movement = {'region_of': {1:1, 2:2, 3:3}, 'oceans': []}
        return classify_water(grid, land, owners, movement)[1]

    def test_strait_two_banks_two_wider_mouths_at_two_resolutions(self):
        candidate = {(x,y) for x in range(12,15) for y in range(14,17)}
        water = candidate | {(x,y) for x in list(range(1,12))+list(range(15,30)) for y in range(2,29)}
        for factor in (1, 2):
            result = self.classify(water, candidate, factor)
            self.assertEqual(result['kind'], 'strait', result)
            self.assertEqual(result['mouth_count'], 2)

    def test_gulf_single_restricted_mouth(self):
        candidate = {(x,y) for x in range(3,10) for y in range(10,17)} | {(10,13),(11,13)}
        water = candidate | {(x,y) for x in range(12,30) for y in range(1,30)}
        for factor in (1, 2):
            result = self.classify(water, candidate, factor)
            self.assertEqual(result['kind'], 'gulf', result)

    def test_enclosed_lake_is_sea_not_gulf(self):
        water = {(x,y) for x in range(10,20) for y in range(10,20)}
        self.assertEqual(self.classify(water, water)['kind'], 'sea')

    def test_open_ocean_and_high_ocean_override(self):
        water = {(x,y) for x in range(31) for y in range(31)}
        candidate = {(x,y) for x in range(10,20) for y in range(10,20)}
        self.assertEqual(self.classify(water, candidate)['kind'], 'ocean')
        grid, land, owners = raster(31, 31, candidate, candidate)
        result = classify_water(grid, land, owners, {'region_of':{1:1}, 'oceans':[{'id':1}]})
        self.assertEqual(result[1]['kind'], 'ocean')

    def test_all_code_patterns_and_uniqueness(self):
        provinces = [dict(id=i, terrain='water', hex_count=10, neighbors=[])
                     for i in range(1,5)]
        classes = {i:{'kind':kind, 'reason':'fixture'} for i,kind in
                   enumerate(['ocean','sea','gulf','strait'],1)}
        assign_names(provinces, build_high_oceans(provinces), 42, classes)
        names = [p['name'] for p in provinces]
        self.assertEqual(len(set(names)), 4)
        self.assertTrue(names[0].endswith('O'))
        self.assertTrue(names[1].endswith('S'))
        self.assertTrue(names[2].startswith('GO'))
        self.assertTrue(names[3].startswith('SO'))
