"""Equal-area latitude-ring cells on a closed sphere, with a rectangular display.

The cells are spherical trapezoids (triangles at the poles), not regular hexes.
Shared parallels are subdivided at BOTH rings' meridians: every graph edge has
a real positive-length boundary. Point contacts at a pole are not adjacency.
"""
import math
import random


class SphereGrid:
    topology = 'sphere'
    wrap_x = True

    def __init__(self, count, aspect=1.5):
        if count < 12:
            raise ValueError('Sphere topology requires at least 12 cells')
        self.count = count
        # Approximately isotropic cells; aspect affects display only.
        rows = max(2, round(math.sqrt(math.pi * count / 4)))
        weights = [math.sin(math.pi * (r + .5) / rows) for r in range(rows)]
        quotas = [(count - 3 * rows) * w / sum(weights) for w in weights]
        sizes = [3 + math.floor(q) for q in quotas]
        for r in sorted(range(rows), key=lambda r: (-(quotas[r] % 1), r))[:count - sum(sizes)]:
            sizes[r] += 1
        self.row_sizes = sizes
        self.width = max(sizes)
        self.display_width = math.sqrt(count * aspect) * 3
        self.display_height = self.display_width / aspect
        self.centers, self.xyz, self.lon_lat = [], [], []
        self.render_edges = [[] for _ in range(count)]
        self.neighbors = [set() for _ in range(count)]
        self.flat_neighbors = [set() for _ in range(count)]
        self.edge_lengths = [{} for _ in range(count)]
        self.area_per_cell = 4 * math.pi / count
        self.length_scale = math.sqrt(count / (4 * math.pi))
        self.latitude_bounds = [math.pi / 2]
        self.row_starts = []
        ring_pieces = []
        start = 0
        for row, n in enumerate(sizes):
            self.row_starts.append(start)
            north = self.latitude_bounds[-1]
            south = math.asin(max(-1., 1 - 2 * (start + n) / count))
            self.latitude_bounds.append(south)
            lat = math.asin(1 - 2 * (start + n / 2) / count)
            offset = .5 * (row % 2)
            for col in range(n):
                fraction = ((col + offset + .5) / n) % 1
                lon = fraction * 2 * math.pi - math.pi
                self.lon_lat.append((lon, lat))
                self.xyz.append((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)))
                self.centers.append(self.point(fraction, lat))
            cuts = sorted({0., 1., *(round(((j + offset) / n) % 1, 12) for j in range(n))})
            pieces = [(a, b, start + math.floor((a + b) / 2 * n - offset) % n)
                      for a, b in zip(cuts, cuts[1:])]
            ring_pieces.append(pieces)
            for a, b, cell in pieces:
                self.render_edges[cell].extend([(self.point(b, north), self.point(b, south)),
                                                (self.point(a, south), self.point(a, north))])
            for j, piece in enumerate(pieces):
                other = pieces[(j + 1) % len(pieces)]
                self.connect(piece[2], other[2], north - south, flat=j + 1 < len(pieces))
            start += n
        # Shared latitude edges, split into exactly matching segments.
        for row in range(rows + 1):
            upper = ring_pieces[row - 1] if row else []
            lower = ring_pieces[row] if row < rows else []
            cuts = sorted({a for pieces in (upper, lower) for a, _, _ in pieces} | {1.})
            ui = li = 0
            lat = self.latitude_bounds[row]
            for a, b in zip(cuts, cuts[1:]):
                mid = (a + b) / 2
                while upper and upper[ui][1] < mid:
                    ui += 1
                while lower and lower[li][1] < mid:
                    li += 1
                left, right = self.point(a, lat), self.point(b, lat)
                if upper:
                    self.render_edges[upper[ui][2]].append((right, left))
                if lower:
                    self.render_edges[lower[li][2]].append((left, right))
                if upper and lower:
                    self.connect(upper[ui][2], lower[li][2], 2 * math.pi * (b - a) * math.cos(lat))
        self.neighbors = [sorted(n) for n in self.neighbors]
        self.flat_neighbors = [sorted(n) for n in self.flat_neighbors]

    def point(self, longitude_fraction, latitude):
        return (round(longitude_fraction * self.display_width, 9),
                round((math.pi / 2 - latitude) / math.pi * self.display_height, 9))

    def connect(self, a, b, length, flat=True):
        if a == b:
            return
        for x, y in ((a, b), (b, a)):
            self.neighbors[x].add(y)
            self.edge_lengths[x][y] = self.edge_lengths[x].get(y, 0) + length * self.length_scale
            if flat:
                self.flat_neighbors[x].add(y)

    def distance2(self, a, b):
        dot = sum(x * y for x, y in zip(self.xyz[a], self.xyz[b]))
        angle = math.acos(max(-1., min(1., dot)))
        return angle * angle * self.length_scale ** 2 * 12

    def perimeter_bound(self, area):
        # Spherical isoperimetric bound, in units where one cell has area 1.
        return math.sqrt(max(0., 4 * math.pi * area * (1 - area / self.count)))

    def metadata(self):
        return {'layout': 'equal-area-latitude-rings', 'topology': 'sphere',
                'projection': 'equirectangular', 'hex_count': self.count,
                'cell_count': self.count, 'wrap_x': True, 'row_sizes': self.row_sizes,
                'latitude_bounds_radians': self.latitude_bounds,
                'cell_area_steradians': self.area_per_cell,
                'cell_longitude_latitude_radians': self.lon_lat,
                'cell_neighbors': self.neighbors,
                'note': 'Cells are spherical trapezoids, with triangular polar cells; hex_count is the legacy cell-count parameter.'}


def elevation_values(config, grid):
    """Coherent 3D value noise sampled on the unit sphere (no UV seam)."""
    rng = random.Random(f'{config.seed}:sphere-elevation')
    values = [0.] * grid.count
    for octave in range(5):
        scale = 2 * math.pi * config.landmass_scale / 2 ** octave
        amplitude = config.roughness ** octave
        lattice = {}
        def value(key):
            if key not in lattice:
                lattice[key] = rng.random()
            return lattice[key]
        for i, position in enumerate(grid.xyz):
            coordinates = [v / scale for v in position]
            base = [math.floor(v) for v in coordinates]
            t = [v - b for v, b in zip(coordinates, base)]
            t = [v * v * (3 - 2 * v) for v in t]
            total = 0.
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        total += value((base[0] + dx, base[1] + dy, base[2] + dz)) * (t[0] if dx else 1-t[0]) * (t[1] if dy else 1-t[1]) * (t[2] if dz else 1-t[2])
            values[i] += amplitude * total
    return values
