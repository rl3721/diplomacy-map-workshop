import unittest
from dataclasses import replace
from generator import Config, Grid, elevation, clean_terrain, partition, measure
from profiles import targets_for


class ProfileTests(unittest.TestCase):
    def test_player_scaling_and_overrides(self):
        self.assertEqual(targets_for(Config())['province_count'], 99)
        for players in (5, 7, 10, 20):
            for ratio in (.8, 1, 1.2):
                self.assertEqual(targets_for(Config(players=players, size_ratio=ratio))['province_count'], round(players * 14.1 * ratio))
        self.assertEqual(targets_for(Config(province_count=75))['province_count'], 75)
        for field in ('size_ratio', 'inland_ratio', 'connectivity_ratio'):
            with self.assertRaises(ValueError):
                replace(Config(), **{field: 1.21}).validate()

    def test_terrain_independent_of_division(self):
        c = Config(hex_count=1200, province_count=20, min_land_component=20, min_water_component=20)
        g = Grid(c.hex_count, c.aspect_ratio)
        first = elevation(c, g)
        self.assertEqual(first, elevation(replace(c, players=10, division_seed=99, inland_ratio=.8, connectivity_ratio=1.2), g))
        terrain, _ = clean_terrain(first[1], g, c)
        owners, sizes = partition(terrain, g, c)
        other, _ = partition(terrain, g, replace(c, division_seed=99))
        self.assertNotEqual(owners, other)
        self.assertTrue(measure(owners, terrain, g, sizes, c)['valid'])

    def test_wrap_adjacency_and_connected_partition(self):
        c = Config(hex_count=1200, province_count=20, wrap_x=True, min_land_component=30, min_water_component=30)
        g = Grid(c.hex_count, c.aspect_ratio, True)
        self.assertIn(g.width - 1, g.neighbors[0])
        for cell, neighbors in enumerate(g.neighbors):
            for nb in neighbors:
                self.assertIn(cell, g.neighbors[nb])
        terrain, _ = clean_terrain(elevation(c, g)[1], g, c)
        owners, sizes = partition(terrain, g, c)
        self.assertTrue(measure(owners, terrain, g, sizes, c)['valid'])

    def test_adjusted_targets(self):
        base = targets_for(Config())
        adjusted = targets_for(Config(inland_ratio=.8, connectivity_ratio=1.2))
        self.assertAlmostEqual(adjusted['inland_target'], base['inland_target'] * .8)
        self.assertAlmostEqual(adjusted['degree_means']['coastal'], base['degree_means']['coastal'] * 1.2)


if __name__ == '__main__':
    unittest.main()
