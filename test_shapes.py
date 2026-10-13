import random
import unittest
from dataclasses import replace

from generator import Config, Grid, components, repair_boundaries
from shapes import region_shape, shape_error


class ShapeTests(unittest.TestCase):
    def test_thin_extension_detected_and_terrain_constraint_distinguished(self):
        grid = Grid(240, 1.5)
        # A straight, interior chain through otherwise available land.
        cells = list(range(grid.width * 4 + 3, grid.width * 4 + 13))
        owners = [1] * grid.count
        for cell in cells:
            owners[cell] = 0
        free_land = [True] * grid.count
        first = region_shape(cells, owners, free_land, grid, 0)
        self.assertEqual(first['internal_diameter_lower_bound'], 9)
        self.assertEqual(first['avoidable_thin_hex_fraction'], 1)
        self.assertGreater(first['single_hex_neck_fraction'], .4)
        island = [owner == 0 for owner in owners]
        second = region_shape(cells, owners, island, grid, 0)
        self.assertEqual(second['avoidable_thin_hex_fraction'], 0)
        self.assertLess(shape_error(second, .3), shape_error(first, .3))

    def test_repair_removes_finger_without_disconnect_or_terrain_change(self):
        grid = Grid(400, 1.5)
        owners = [int(cell % grid.width >= grid.width // 2) for cell in range(grid.count)]
        row = 5
        for col in range(grid.width // 2, grid.width - 2):
            owners[row * grid.width + col] = 0
        terrain = [True] * grid.count
        targets = [owners.count(pid) for pid in (0, 1)]
        seeds = [grid.width * 4 + 2, grid.width * 4 + grid.width - 2]

        def perimeter():
            return sum(owners[c] != owners[n] for c in range(grid.count) for n in grid.neighbors[c])

        before = perimeter()
        repair_boundaries(owners, terrain, grid, targets, seeds,
                          Config(shape_regularity=1, size_flexibility=1, repair_passes=20), random.Random(1))
        self.assertLess(perimeter(), before)
        self.assertEqual(len(components(owners, grid)), 2)
        self.assertEqual([owners[s] for s in seeds], [0, 1])
        self.assertTrue(all(terrain))

    def test_wrap_shape_traversal(self):
        grid = Grid(240, 1.5, True)
        cells = [0, grid.width - 1]
        owners = [1] * grid.count
        for cell in cells:
            owners[cell] = 0
        result = region_shape(cells, owners, [True] * grid.count, grid, 0)
        self.assertEqual(result['internal_diameter_lower_bound'], 1)

    def test_shape_controls_validate(self):
        for name in ('shape_regularity', 'size_flexibility'):
            for value in (-.1, 1.1):
                with self.assertRaises(ValueError):
                    replace(Config(), **{name: value}).validate()


if __name__ == '__main__':
    unittest.main()
