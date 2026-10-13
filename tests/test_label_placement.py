from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from mapgen.generator import outline_polygons, write_svg
from mapgen.label_placement import inside, interior_anchor, projected_labels, signed_area
from mapgen.sphere import SphereGrid


class LabelPlacementTests(unittest.TestCase):
    def test_concave_province_and_hole(self):
        shapes = [
            [[(0, 0), (40, 0), (40, 10), (10, 10), (10, 40), (0, 40)]],
            [[(0, 0), (40, 0), (40, 40), (0, 40)],
             [(10, 10), (10, 30), (30, 30), (30, 10)]],
        ]
        for rings in shapes:
            x, y, clearance = interior_anchor(rings)
            self.assertTrue(inside(x, y, rings[0]))
            self.assertTrue(all(not inside(x, y, hole) for hole in rings[1:]))
            self.assertGreater(clearance, 4.9)

    def test_split_cell_gets_one_label_on_each_display_side(self):
        grid = SphereGrid(600)
        row = 3  # offset ring: its last cell is cut in two by the display seam
        cell = grid.row_starts[row] + grid.row_sizes[row] - 1
        owners = [1] * grid.count
        owners[cell] = 0
        rings = outline_polygons(grid, owners)[0]
        anchors = list(projected_labels(rings, '1'))
        self.assertEqual(len(anchors), 2)
        self.assertLess(min(x for x, _, _ in anchors), grid.display_width * .1)
        self.assertGreater(max(x for x, _, _ in anchors), grid.display_width * .9)
        for ring in rings:
            self.assertEqual(sum(inside(x, y, ring) for x, y, _ in anchors), 1)

    def test_polar_strip_uses_display_center(self):
        grid = SphereGrid(600)
        owners = [0 if i < grid.row_sizes[0] else 1 for i in range(grid.count)]
        rings = outline_polygons(grid, owners)[0]
        x, y, font = next(projected_labels(rings, '99'))
        self.assertAlmostEqual(x, grid.display_width / 2)
        self.assertAlmostEqual(y, grid.point(0, grid.latitude_bounds[1])[1] / 2)
        self.assertGreater(font, 0)

    def test_label_box_fits_tiny_piece_and_avoids_hole(self):
        for rings in ([[ (0, 0), (.2, 0), (.2, 8), (0, 8)]],
                      [[(0, 0), (30, 0), (30, 30), (0, 30)],
                       [(5, 5), (5, 25), (25, 25), (25, 5)]]):
            for x, y, font in projected_labels(rings, '123'):
                self.assertGreater(font, 0)
                for dx in (-1.2 * font, 1.2 * font):
                    for dy in (-.75 * font, .75 * font):
                        self.assertEqual(sum(inside(x + dx, y + dy, ring) for ring in rings) % 2, 1)

    def test_svg_text_matches_its_visible_province(self):
        grid = SphereGrid(97)
        labels = [i % 9 for i in range(grid.count)]
        polygons = outline_polygons(grid, labels)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'map.svg'
            write_svg(path, 'Label regression', grid, labels, dict.fromkeys(range(9), '#aac'), True)
            texts = ET.parse(path).findall('{http://www.w3.org/2000/svg}text')
            self.assertEqual(len(texts), sum(signed_area(ring) > 0 for rings in polygons.values() for ring in rings))
            for text in texts:
                x, y = float(text.attrib['x']), float(text.attrib['y'])
                self.assertEqual(sum(inside(x, y, ring) for ring in polygons[int(text.text) - 1]) % 2, 1)


if __name__ == '__main__':
    unittest.main()
