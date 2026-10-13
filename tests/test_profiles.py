import unittest
from dataclasses import replace
from mapgen.generator import Config, Grid, elevation, clean_terrain, partition, measure
from mapgen.profiles import targets_for


class ProfileTests(unittest.TestCase):
    def test_relative_cleanup_and_custom_terrain(self):
        for count, threshold in ((500, 18), (5000, 180), (50000, 1800)):
            config = Config(hex_count=count)
            self.assertEqual(config.resolved().min_land_component, threshold)
            self.assertEqual(config.resolved().min_water_component, threshold)
        # Resolution changes preserve removal behavior for proportionally-sized components.
        from types import SimpleNamespace
        for count in (100, 1000):
            grid = SimpleNamespace(count=count, neighbors=[[n for n in (i-1, i+1) if 0 <= n < count] for i in range(count)])
            terrain = [i < count * .03 for i in range(count)]
            self.assertFalse(any(clean_terrain(terrain, grid, Config(hex_count=count))[0]))
            terrain = [i < count * .04 for i in range(count)]
            self.assertEqual(clean_terrain(terrain, grid, Config(hex_count=count))[0], terrain)
        source = Config(hex_count=600, terrain_style='islands').resolved()
        custom = replace(source, terrain_style='custom')
        self.assertEqual(elevation(source, Grid(600, 1.5)), elevation(custom, Grid(600, 1.5)))

    def test_peninsula_default_preserves_province_targets(self):
        baseline = targets_for(Config(terrain_style='peninsula'))
        self.assertEqual(Config().terrain_style, 'peninsula')
        self.assertEqual(Config().resolved().land_fraction, .4)
        for terrain in ('peninsula', 'continental', 'islands'):
            self.assertEqual(targets_for(Config(terrain_style=terrain)), baseline)
        self.assertEqual(baseline['province_count'], 99)
        self.assertAlmostEqual(baseline['inland_target'], .266317920953937, places=4)
        self.assertNotEqual(targets_for(Config(province_style='islands'))['inland_target'], baseline['inland_target'])

    def test_player_scaling_and_overrides(self):
        self.assertEqual(targets_for(Config())['province_count'], 99)
        for players in (5, 7, 10, 20):
            for ratio in (.8, 1, 1.2):
                self.assertEqual(targets_for(Config(players=players, size_ratio=ratio))['province_count'], round(players * 14.1 * ratio))
        self.assertEqual(targets_for(Config(province_count=75))['province_count'], 75)
        for field in ('size_ratio', 'inland_ratio', 'connectivity_ratio'):
            with self.assertRaises(ValueError):
                replace(Config(), **{field: 1.51 if field == 'size_ratio' else 1.21}).validate()

    def test_terrain_independent_of_division(self):
        c = Config(hex_count=1200, province_count=20, min_land_component=20, min_water_component=20)
        g = Grid(c.hex_count, c.aspect_ratio)
        first = elevation(c, g)
        self.assertEqual(first, elevation(replace(c, players=10, division_seed=99, inland_ratio=.8, connectivity_ratio=1.2), g))
        terrain, _ = clean_terrain(first[1], g, c)
        owners, sizes = partition(terrain, g, c)
        other, _ = partition(terrain, g, replace(c, division_seed=99))
        self.assertNotEqual(owners, other)
        self.assertTrue(measure(owners, terrain, g, sizes, c)['structurally_valid'])

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
