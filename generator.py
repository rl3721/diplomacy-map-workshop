"""Deterministic hex terrain and connected province generation. Standard library only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, fields, replace
import heapq
import html
import json
import math
from pathlib import Path
import random
import statistics
import time
from types import SimpleNamespace

from scoring import COMPONENTS, score_map
from profiles import STYLES, targets_for
from shapes import region_shape


@dataclass
class Config:
    players: int = 7
    size_ratio: float = 1.0
    inland_ratio: float = 1.0
    connectivity_ratio: float = 1.0
    terrain_style: str = 'peninsula'
    reference_profile: str = 'auto'
    division_seed: int = 42
    candidates: int = 12
    wrap_x: bool = False
    hex_count: int = 50000
    aspect_ratio: float = 1.5
    seed: int = 42
    land_fraction: float = -1.0
    landmass_scale: float = -1.0
    roughness: float = -1.0
    min_land_component: int = 180
    min_water_component: int = 180
    province_count: int = 0
    land_province_fraction: float = -1.0
    size_variation: float = 0.4
    compactness: float = 0.8
    shape_regularity: float = 0.8
    size_flexibility: float = 0.3
    repair_passes: int = 12
    weight_degree: float = 40.0
    weight_composition: float = 20.0
    weight_global: float = 20.0
    weight_size: float = 15.0
    weight_shape: float = 5.0
    degree_tolerance: float = 2.0
    composition_tolerance: float = 0.35
    path_tolerance: float = 0.35
    fragmentation_tolerance: float = 0.25
    bottleneck_tolerance: float = 0.15
    size_tolerance: float = math.log(1.5)
    shape_tolerance: float = 0.6

    def validate(self):
        for name in ('hex_count', 'seed', 'min_land_component', 'min_water_component',
                     'province_count', 'repair_passes', 'players', 'division_seed', 'candidates'):
            if type(getattr(self, name)) is not int:
                raise ValueError(f'{name} must be an integer')
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in ('terrain_style', 'reference_profile', 'wrap_x'):
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f'{field.name} must be a finite number')
        if not 1 <= self.hex_count <= 500000:
            raise ValueError('hex_count must be between 1 and 500000')
        if self.terrain_style not in STYLES or self.reference_profile not in ('auto', 'classic', 'peninsula', 'world'):
            raise ValueError('Invalid terrain_style or reference_profile')
        if type(self.wrap_x) is not bool:
            raise ValueError('wrap_x must be true or false')
        if not 1 <= self.players <= 100 or not 1 <= self.candidates <= 100:
            raise ValueError('players and candidates must be between 1 and 100')
        for name in ('size_ratio', 'inland_ratio', 'connectivity_ratio'):
            if not .8 <= getattr(self, name) <= 1.2:
                raise ValueError(f'{name} must be between 0.8 and 1.2')
        if not 0 <= self.province_count <= self.hex_count:
            raise ValueError('province_count must be 0 (automatic) or between 1 and hex_count')
        if targets_for(self)['province_count'] > self.hex_count:
            raise ValueError('Not enough hexes for the player-based province count; increase hex_count or override province_count')
        if not 0.2 <= self.aspect_ratio <= 5:
            raise ValueError('aspect_ratio must be between 0.2 and 5')
        for name in ('land_fraction', 'land_province_fraction', 'roughness', 'compactness', 'shape_regularity', 'size_flexibility'):
            if name in ('land_fraction', 'land_province_fraction', 'roughness') and getattr(self, name) == -1:
                continue
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f'{name} must be between 0 and 1')
        if self.landmass_scale != -1 and not 0.01 <= self.landmass_scale <= 2:
            raise ValueError('landmass_scale must be between 0.01 and 2')
        if not 0 <= self.size_variation <= 2:
            raise ValueError('size_variation must be between 0 and 2')
        if min(self.min_land_component, self.min_water_component) < 0:
            raise ValueError('component thresholds must be nonnegative')
        if not 0 <= self.repair_passes <= 30:
            raise ValueError('repair_passes must be between 0 and 30')
        weights = [getattr(self, 'weight_' + name) for name in COMPONENTS]
        if min(weights) < 0 or sum(weights) <= 0:
            raise ValueError('Scoring weights must be nonnegative with at least one positive weight')
        for field in fields(self):
            if field.name.endswith('_tolerance') and getattr(self, field.name) <= 0:
                raise ValueError(f'{field.name} must be positive')

    def resolved(self):
        preset = STYLES[self.terrain_style]
        target = targets_for(self)
        return replace(self, province_count=target['province_count'],
                       land_province_fraction=target['land_province_fraction'],
                       **{key: preset[key] if getattr(self, key) == -1 else getattr(self, key)
                          for key in ('land_fraction', 'landmass_scale', 'roughness')})


class Grid:
    def __init__(self, count, aspect, wrap_x=False):
        self.width = max(1, min(count, round(math.sqrt(count * aspect * math.sqrt(3) / 2))))
        self.wrap_x = wrap_x
        if wrap_x:
            divisors = [width for width in range(3, count + 1) if count % width == 0 and count // width >= 2]
            if not divisors:
                raise ValueError('Horizontal wrap needs a hex count with at least 3 columns and 2 complete rows')
            self.width = min(divisors, key=lambda width: abs(math.log(width / self.width)))
        self.count = count
        self.centers = [(2 * (i % self.width) + ((i // self.width) % 2),
                         3 * (i // self.width)) for i in range(count)]
        self.neighbors = []
        self.flat_neighbors = []
        for i in range(count):
            row, col = divmod(i, self.width)
            shift = row % 2
            candidates = [(row, col - 1), (row, col + 1),
                          (row - 1, col - 1 + shift), (row - 1, col + shift),
                          (row + 1, col - 1 + shift), (row + 1, col + shift)]
            flat = [r * self.width + c for r, c in candidates
                    if r >= 0 and 0 <= c < self.width and r * self.width + c < count]
            self.flat_neighbors.append(flat)
            wrapped = [r * self.width + (c % self.width) for r, c in candidates
                       if 0 <= r < count // self.width] if wrap_x else flat
            self.neighbors.append(sorted(set(wrapped) - {i}))

    def vertices(self, i):
        x, y = self.centers[i]
        return [(x + dx, y + dy) for dx, dy in ((1, -1), (1, 1), (0, 2),
                                               (-1, 1), (-1, -1), (0, -2))]

    def distance2(self, a, b):
        x, y = self.centers[a]
        xx, yy = self.centers[b]
        dx = abs(x - xx)
        if self.wrap_x:
            dx = min(dx, 2 * self.width - dx)
        return 3 * dx ** 2 + (y - yy) ** 2


def components(labels, grid):
    seen = bytearray(grid.count)
    result = []
    for start in range(grid.count):
        if seen[start]:
            continue
        seen[start] = 1
        cells = [start]
        for cell in cells:
            for nb in grid.neighbors[cell]:
                if not seen[nb] and labels[nb] == labels[start]:
                    seen[nb] = 1
                    cells.append(nb)
        result.append(cells)
    return result


def elevation(config, grid):
    config = config.resolved()
    rng = random.Random(f'{config.seed}:elevation')
    span = max(grid.width * math.sqrt(3), math.ceil(grid.count / grid.width) * 1.5)
    values = [0.0] * grid.count
    stretch_x, stretch_y = STYLES[config.terrain_style]['stretch']
    for octave in range(5):
        scale = span * config.landmass_scale / (2 ** octave)
        amplitude = config.roughness ** octave
        lattice = {}
        period = max(1, round(grid.width * math.sqrt(3) / (scale * stretch_x)))

        def value(x, y):
            if grid.wrap_x:
                x %= period
            if (x, y) not in lattice:
                lattice[x, y] = rng.random()
            return lattice[x, y]

        for i, (cx, cy) in enumerate(grid.centers):
            x = cx / (2 * grid.width) * period if grid.wrap_x else cx * math.sqrt(3) / (2 * scale * stretch_x)
            y = cy / (2 * scale * stretch_y)
            ix, iy = math.floor(x), math.floor(y)
            tx, ty = x - ix, y - iy
            tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
            low = value(ix, iy) * (1 - tx) + value(ix + 1, iy) * tx
            high = value(ix, iy + 1) * (1 - tx) + value(ix + 1, iy + 1) * tx
            values[i] += amplitude * (low * (1 - ty) + high * ty)
    low, high = min(values), max(values)
    values = [(x - low) / (high - low or 1) for x in values]
    land_count = round(config.land_fraction * grid.count)
    order = sorted(range(grid.count), key=lambda i: (values[i], i))
    terrain = [False] * grid.count
    for i in order[grid.count - land_count:]:
        terrain[i] = True
    water_count = grid.count - land_count
    sea_level = ((values[order[water_count - 1]] + values[order[water_count]]) / 2
                 if 0 < water_count < grid.count else (1.000001 if water_count else -0.000001))
    return values, terrain, sea_level


def clean_terrain(terrain, grid, config):
    cleaned = terrain.copy()
    flips = 0
    # Flipping one component merges it with all adjacent opposite-type components.
    # Component count strictly decreases, so this cannot oscillate.
    while True:
        groups = components(cleaned, grid)
        small = [g for g in groups if len(g) < (config.min_land_component if cleaned[g[0]]
                                                else config.min_water_component)]
        if not small or len(groups) == 1:
            break
        group = min(small, key=lambda g: (len(g), g[0]))
        for cell in group:
            cleaned[cell] = not cleaned[cell]
        flips += len(group)
    return cleaned, flips


def allocate(groups, count):
    if count < len(groups) or count > sum(map(len, groups)):
        raise ValueError(f'Cannot allocate {count} provinces to {len(groups)} terrain components '
                         f'containing {sum(map(len, groups))} hexes. Increase cleanup thresholds, '
                         'change land_province_fraction/province_count, or use another seed.')
    counts = [1] * len(groups)
    heap = [(-len(g) / 2, i) for i, g in enumerate(groups) if len(g) > 1]
    heapq.heapify(heap)
    for _ in range(count - len(groups)):
        _, i = heapq.heappop(heap)
        counts[i] += 1
        if counts[i] < len(groups[i]):
            heapq.heappush(heap, (-len(groups[i]) / (counts[i] + 1), i))
    return counts


def size_targets(total, count, variation, rng):
    weights = [rng.lognormvariate(0, variation) for _ in range(count)]
    extra = total - count
    quotas = [extra * w / sum(weights) for w in weights]
    sizes = [1 + math.floor(q) for q in quotas]
    ranking = sorted(range(count), key=lambda i: (-(quotas[i] % 1), i))
    for i in ranking[:total - sum(sizes)]:
        sizes[i] += 1
    return sizes


def partition(terrain, grid, config, candidate_index=0):
    config = config.resolved()
    rng = random.Random(f'{config.division_seed}:provinces:{candidate_index}')
    groups = components(terrain, grid)
    land = [g for g in groups if terrain[g[0]]]
    water = [g for g in groups if not terrain[g[0]]]
    land_count = round(config.province_count * config.land_province_fraction)
    if not water:
        land_count = config.province_count
    if not land:
        land_count = 0
    groups = land + water
    allocations = allocate(land, land_count) + allocate(water, config.province_count - land_count)
    owners = [-1] * grid.count
    targets, seeds = [], []
    for group, count in zip(groups, allocations):
        base = len(targets)
        local_targets = size_targets(len(group), count, config.size_variation, rng)
        targets.extend(local_targets)
        # Farthest-point placement on a bounded random sample avoids O(H*P) seed scans.
        coast = [cell for cell in group if terrain[cell] and any(not terrain[n] for n in grid.neighbors[cell])]
        coast_count = min(len(coast), max(1, round(count * (1 - targets_for(config)['inland_target'])))) if coast else 0
        pool = rng.sample(group, min(len(group), max(256, count * 12)))
        coastal_pool = rng.sample(coast, min(len(coast), max(256, count * 12)))
        local_seeds = []
        nearest = {cell: float('inf') for cell in set(pool + coastal_pool)}
        for index in range(count):
            choices = coastal_pool if index < coast_count else pool
            available = [cell for cell in choices if cell not in local_seeds]
            seed = rng.choice(available) if not local_seeds else max(available, key=lambda cell: (nearest[cell], -cell))
            local_seeds.append(seed)
            for cell in nearest:
                nearest[cell] = min(nearest[cell], grid.distance2(cell, seed))
        seeds.extend(local_seeds)
        frontier = []
        allowed = set(group)
        radii = [math.sqrt(t) for t in local_targets]
        for pid, seed in enumerate(local_seeds):
            owners[seed] = base + pid

        def expose(pid, cell, travel):
            for nb in grid.neighbors[cell]:
                if nb in allowed and owners[nb] == -1:
                    same = sum(owners[n] == base + pid for n in grid.neighbors[nb])
                    distance = travel + 1 + (1 - config.compactness) * rng.random() * .3
                    # Spatial competition replaces size-deficit scheduling: a trapped region
                    # may remain small instead of chasing its quota through narrow corridors.
                    perimeter_cost = config.shape_regularity * (6 - 2 * same)
                    priority = (distance + perimeter_cost) / radii[pid]
                    heapq.heappush(frontier, (priority, nb, pid, distance))

        for pid, seed in enumerate(local_seeds):
            expose(pid, seed, 0)
        while frontier:
            _, cell, pid, travel = heapq.heappop(frontier)
            if owners[cell] != -1:
                continue
            owners[cell] = base + pid
            expose(pid, cell, travel)
    if -1 in owners:
        raise RuntimeError('Partition left unassigned hexes')
    repair_boundaries(owners, terrain, grid, targets, seeds, config, rng)
    return owners, targets


def repair_boundaries(owners, terrain, grid, targets, seeds, config, rng):
    """Descending size/shape energy, with a sufficient donor-connectivity test."""
    sizes = Counter(owners)
    perimeter_scales = [2 * math.sqrt(12 * t) for t in targets]

    def size_cost(size, target):
        error = max(0, abs(math.log(size / target)) - math.log1p(config.size_flexibility))
        return 2 * error * error

    for _ in range(config.repair_passes):
        moved = 0
        boundary = [i for i in range(grid.count) if any(owners[n] != owners[i] for n in grid.neighbors[i])]
        rng.shuffle(boundary)
        for cell in boundary:
            old = owners[cell]
            if sizes[old] <= 1 or cell == seeds[old]:
                continue
            same = {n for n in grid.neighbors[cell] if owners[n] == old}
            # Sufficient local test: all donor neighbors remain linked without this cell.
            if not same:
                continue
            reached = {min(same)}
            stack = list(reached)
            for nb in stack:
                for nn in grid.neighbors[nb]:
                    if nn in same and nn not in reached:
                        reached.add(nn)
                        stack.append(nn)
            if reached != same:
                continue
            choices = sorted({owners[n] for n in grid.neighbors[cell]
                              if owners[n] != old and terrain[n] == terrain[cell]})
            best, improvement = None, 0
            # Coastlines and map edges are largely imposed by terrain. Internal
            # province borders have four times their influence on repair.
            edge_weight = sum(1 if terrain[n] == terrain[cell] else .25 for n in grid.neighbors[cell]) + .25 * (6 - len(grid.neighbors[cell]))
            for new in choices:
                before = size_cost(sizes[old], targets[old]) + size_cost(sizes[new], targets[new])
                after = size_cost(sizes[old] - 1, targets[old]) + size_cost(sizes[new] + 1, targets[new])
                new_touch = sum(owners[n] == new for n in grid.neighbors[cell])
                perimeter_delta = ((2 * len(same) - edge_weight) / perimeter_scales[old]
                                   + (edge_weight - 2 * new_touch) / perimeter_scales[new])
                # Discourage remote appendages as well as jagged borders.
                radius_delta = (grid.distance2(cell, seeds[new]) / targets[new] ** 2
                                - grid.distance2(cell, seeds[old]) / targets[old] ** 2) / 12
                after += config.shape_regularity * (2 * perimeter_delta + radius_delta)
                if before - after > improvement + 1e-12:
                    best, improvement = new, before - after
            if best is not None:
                owners[cell] = best
                sizes[old] -= 1
                sizes[best] += 1
                moved += 1
        if not moved:
            break


def summary(values):
    if not values:
        return {'count': 0, 'min': None, 'max': None, 'mean': None, 'modes': [], 'histogram': {}}
    histogram = Counter(values)
    return {'count': len(values), 'min': min(values), 'max': max(values),
            'mean': statistics.mean(values), 'median': statistics.median(values),
            'standard_deviation': statistics.pstdev(values),
            'modes': sorted(k for k, v in histogram.items() if v == max(histogram.values())),
            'histogram': dict(sorted(histogram.items()))}


CLASSIC = {
    'inland': {4: 1, 5: 6, 6: 4, 7: 3},
    'coastal': {2: 1, 3: 2, 4: 6, 5: 18, 6: 10, 7: 5},
    'sea': {3: 1, 4: 3, 5: 4, 6: 5, 7: 2, 8: 1, 9: 2, 11: 1},
}


def measure(owners, terrain, grid, targets, config=None):
    groups = components(owners, grid)
    if len(groups) != len(targets) or len(set(owners)) != len(targets):
        raise RuntimeError('Province connectivity/count validation failed')
    adjacency = [set() for _ in targets]
    cells_by_id = [[] for _ in targets]
    for cell, pid in enumerate(owners):
        cells_by_id[pid].append(cell)
        for nb in grid.neighbors[cell]:
            if owners[nb] != pid:
                adjacency[pid].add(owners[nb])
    types = [terrain[cells[0]] for cells in cells_by_id]
    provinces = []
    degrees = defaultdict(list)
    efficiencies = []
    for pid, cells in enumerate(cells_by_id):
        if any(terrain[c] != types[pid] for c in cells):
            raise RuntimeError('Mixed land/water province')
        category = 'sea' if not types[pid] else ('coastal' if any(not types[n] for n in adjacency[pid]) else 'inland')
        degrees[category].append(len(adjacency[pid]))
        perimeter = sum(6 - sum(owners[nb] == pid for nb in grid.neighbors[c]) for c in cells)
        compact_perimeter = 2 * math.ceil(math.sqrt(12 * len(cells) - 3))
        efficiency = min(1.0, compact_perimeter / perimeter)
        efficiencies.append(efficiency)
        provinces.append({'id': pid + 1, 'terrain': 'land' if types[pid] else 'water',
                          'category': category, 'hex_count': len(cells), 'target_hex_count': targets[pid],
                          'perimeter_hex_edges': perimeter, 'perimeter_efficiency': efficiency,
                          **region_shape(cells, owners, terrain, grid, pid),
                          'neighbors': sorted(n + 1 for n in adjacency[pid])})
    distances = {}
    for category, baseline in CLASSIC.items():
        values = degrees[category]
        if not values:
            distances[category] = None
            continue
        hist = Counter(values)
        ca = cb = distance = 0
        for degree in range(max(max(hist), max(baseline)) + 1):
            ca += hist[degree] / len(values)
            cb += baseline.get(degree, 0) / sum(baseline.values())
            distance += abs(ca - cb)
        distances[category] = distance
    scoring = score_map(provinces, efficiencies, config or Config())
    score = statistics.mean(100 * max(0, 1 - d / 2) if d is not None else 0 for d in distances.values())
    return {'valid': True, 'province_count': len(targets),
            'province_sizes': summary([len(c) for c in cells_by_id]),
            'degree_statistics': {'all': summary([len(a) for a in adjacency]),
                                  **{k: summary(degrees[k]) for k in CLASSIC}},
            'classic_degree_distance': distances, 'classic_degree_similarity_score': score,
            'size_mean_absolute_log_error': statistics.mean(abs(math.log(len(c) / t)) for c, t in zip(cells_by_id, targets)),
            'scoring': scoring,
            'provinces': provinces}


def outline_paths(grid, labels):
    edges = defaultdict(dict)
    for i, label in enumerate(labels):
        vertices = grid.vertices(i)
        boundary = edges[label]
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            if (b, a) in boundary:
                del boundary[b, a]
            else:
                boundary[a, b] = True
    result = {}
    for label, boundary in edges.items():
        outgoing = defaultdict(set)
        for a, b in boundary:
            outgoing[a].add(b)
        paths = []
        while outgoing:
            start = next(iter(outgoing))
            current = start
            points = [start]
            while True:
                nxt = min(outgoing[current])
                outgoing[current].remove(nxt)
                if not outgoing[current]:
                    del outgoing[current]
                current = nxt
                if current == start:
                    break
                points.append(current)
            paths.append('M' + ' L'.join(f'{x},{y}' for x, y in points) + ' Z')
        result[label] = ' '.join(paths)
    return result


def write_svg(path, title, grid, labels, colors, province_labels=None):
    paths = outline_paths(grid, labels)
    width = (max(x for x, _ in grid.centers) + 3) * math.sqrt(3)
    height = max(y for _, y in grid.centers) + 5
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {height}" role="img">',
             f'<title>{html.escape(title)}</title>', '<rect width="100%" height="100%" fill="#edf2f5"/>',
             '<g transform="translate(1.733 2) scale(1.732050808 1)">']
    for label, d in sorted(paths.items()):
        stroke = '#233d43' if province_labels is not None else colors[label]
        stroke_width = '.18' if province_labels is not None else '.04'
        lines.append(f'<path id="region-{label}" d="{d}" fill="{colors[label]}" fill-rule="evenodd" '
                     f'stroke="{stroke}" stroke-width="{stroke_width}" stroke-linejoin="round"/>')
    lines.append('</g>')
    if province_labels is not None:
        visible_groups = components(labels, SimpleNamespace(count=grid.count, neighbors=grid.flat_neighbors))
        for members in visible_groups:
            pid = labels[members[0]]
            mx = statistics.mean(grid.centers[i][0] for i in members)
            my = statistics.mean(grid.centers[i][1] for i in members)
            center = min(members, key=lambda i: 3 * (grid.centers[i][0] - mx) ** 2 + (grid.centers[i][1] - my) ** 2)
            x, y = grid.centers[center]
            font = min(10, max(2.5, math.sqrt(len(members)) * .3))
            lines.append(f'<text x="{(x + 1) * math.sqrt(3):.3f}" y="{y + 2}" text-anchor="middle" '
                         f'dominant-baseline="central" font-family="sans-serif" font-size="{font:.2f}" '
                         f'fill="#102d35" stroke="white" stroke-width=".6" paint-order="stroke">{pid + 1}</text>')
    lines.append('</svg>')
    path.write_text('\n'.join(lines), encoding='utf-8')


def generate(config, output, progress=print):
    config.validate()
    requested = config
    generation_targets = targets_for(config)
    config = config.resolved()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    progress('1/5 Generating elevation and initial terrain')
    grid = Grid(config.hex_count, config.aspect_ratio, config.wrap_x)
    heights, initial, sea_level = elevation(config, grid)
    progress('2/5 Cleaning small terrain components')
    cleaned, flips = clean_terrain(initial, grid, config)
    # Save intermediates before partition: they remain useful if the requested count is infeasible.
    colors = {}
    for land in (False, True):
        for band in range(12):
            t = band / 11
            a, b = ((31, 74, 111), (147, 204, 218)) if not land else ((199, 217, 155), (65, 106, 73))
            colors[int(land) * 12 + band] = '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(a, b))
    for name, terrain in [('01_elevation.svg', initial), ('02_cleaned.svg', cleaned)]:
        labels = []
        for height, land in zip(heights, terrain):
            relative = ((height - sea_level) / max(1e-9, 1 - sea_level) if land
                        else height / max(1e-9, sea_level))
            labels.append(int(land) * 12 + min(11, max(0, int(relative * 11))))
        write_svg(output / name, name, grid, labels, colors)
    (output / 'parameters.json').write_text(json.dumps(asdict(requested), indent=2), encoding='utf-8')
    # Prevent previous successful output being mistaken for this failed run.
    for name in ('03_provinces.svg', 'report.json', 'map.json', 'index.html'):
        (output / name).unlink(missing_ok=True)
    progress('3/5 Allocating and growing provinces')
    best = None
    candidate_scores = []
    for candidate in range(config.candidates):
        progress(f'3/5 Province candidate {candidate + 1}/{config.candidates}')
        owners, targets = partition(cleaned, grid, config, candidate)
        report = measure(owners, cleaned, grid, targets, config)
        score = report['scoring']['total']
        candidate_scores.append(score)
        if best is None or score > best[0]:
            best = (score, owners, targets, report, candidate)
    _, owners, targets, report, selected = best
    report.update(generation_targets=generation_targets, candidate_scores=candidate_scores,
                  selected_candidate=selected, requested_parameters=asdict(requested))
    report.update({'parameters': asdict(config), 'sea_level': sea_level,
                   'initial_land_fraction': sum(initial) / grid.count,
                   'cleaned_land_fraction': sum(cleaned) / grid.count,
                   'changed_hex_count': sum(a != b for a, b in zip(initial, cleaned)),
                   'cleanup_flip_operations': flips,
                   'terrain_components': {kind: sorted([len(c) for c in components(cleaned, grid)
                                                       if cleaned[c[0]] == flag], reverse=True)
                                          for kind, flag in [('land', True), ('water', False)]}})
    progress('5/5 Exporting province SVG and preview')
    palette = {}
    rng = random.Random(f'{config.seed}:colors')
    for province in report['provinces']:
        hue = rng.randrange(75, 145) if province['terrain'] == 'land' else rng.randrange(190, 220)
        lightness = rng.randrange(66, 84)
        palette[province['id'] - 1] = f'hsl({hue},35%,{lightness}%)'
    write_svg(output / '03_provinces.svg', 'Connected provinces', grid, owners, palette, True)
    report['elapsed_seconds'] = time.perf_counter() - started
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    data = {'schema_version': 2, 'grid': {'layout': 'odd-r', 'width': grid.width, 'hex_count': grid.count, 'wrap_x': grid.wrap_x},
            'elevations': heights, 'initial_land': initial, 'cleaned_land': cleaned,
            'province_ids': [p + 1 for p in owners], 'provinces': report['provinces']}
    (output / 'map.json').write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
    degree = report['degree_statistics']['all']
    scoring = report['scoring']
    score_rows = ''.join(f'<tr><td>{name.capitalize()}</td><td>{part["score"]:.1f}</td>'
                         f'<td>{part["normalized_weight"]:.0%}</td><td>{part["contribution"]:.1f}</td></tr>'
                         for name, part in scoring['components'].items())
    score_warnings = ' '.join(scoring['warnings'])
    shape = scoring['shape']
    shape_lookup = {p['id']: p for p in report['provinces']}
    shape_rows = ''.join(
        f'<tr><td>{pid}</td><td>{shape_lookup[pid]["perimeter_efficiency"]:.2f}</td>'
        f'<td>{shape_lookup[pid]["normalized_internal_diameter"]:.2f}</td>'
        f'<td>{shape_lookup[pid]["avoidable_thin_hex_fraction"]:.1%}</td>'
        f'<td>{shape_lookup[pid]["single_hex_neck_fraction"]:.1%}</td></tr>'
        for pid in shape['worst_province_ids'])
    shape_panel = f'''<section><h2>Province shape checks</h2>
<p>Perimeter efficiency: mean {shape['mean_perimeter_efficiency']:.2f},
worst 10% {shape['worst_decile_perimeter_efficiency']:.2f}, minimum {shape['min_perimeter_efficiency']:.2f} (higher is better).
Review flags: {html.escape(str(shape['flagged_province_ids']))}.</p>
<p>Worst provinces by terrain-adjusted shape error:</p>
<table><thead><tr><th>Province</th><th>Efficiency</th><th>Travel / sqrt(area)</th><th>Avoidable thin cells</th><th>One-hex neck</th></tr></thead>
<tbody>{shape_rows}</tbody></table>
<p>Travel uses a two-sweep diameter lower bound. A one-hex neck is the fraction separated from the
largest remaining piece by removing one hex. Flags identify travel above 4.5, thin cells above 5%,
or neck fraction above 20%; these are review heuristics, and terrain can impose narrow regions.</p></section>'''
    expected = scoring['composition']['expected_counts']
    score_panel = f'''<section><h2>Structural score: {scoring['total']:.1f} / 100</h2>
<table><thead><tr><th>Component</th><th>Score / 100</th><th>Weight</th><th>Points</th></tr></thead>
<tbody>{score_rows}</tbody></table>
<p>Variant-profile targets at {len(targets)} provinces: {expected['inland']:.1f} inland,
{expected['coastal']:.1f} coastal, {expected['sea']:.1f} sea (fractional comparison targets).</p>
<p>Travel distances are normalized by the square root of each graph's province count.
This is a two-dimensional scaling heuristic, not a gameplay-balance guarantee.
Size and shape measure generation quality; other components compare the selected variant profile.</p>
<p>Terrain: {config.terrain_style}. Players: {config.players}. Horizontal wrap: {config.wrap_x}.
Best of {config.candidates} divisions. References: {html.escape(', '.join(generation_targets['members']))}.</p>
<p>{html.escape(score_warnings)}</p></section>'''
    cards = ''.join(f'<section><h2>{title}</h2><a href="{name}">Open SVG</a><img src="{name}" alt="{title}"></section>'
                    for name, title in [('01_elevation.svg', '01 · Elevation / land and water'),
                                        ('02_cleaned.svg', '02 · Small regions cleaned'),
                                        ('03_provinces.svg', '03 · Connected provinces')])
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Province map · seed {config.seed}</title><style>
body{{font:16px system-ui;background:#edf2f5;color:#18343e;margin:0;padding:32px;max-width:1400px;margin:auto}}
h1{{margin-bottom:8px}}p{{line-height:1.6}}section{{background:white;padding:20px;margin:24px 0;border-radius:12px}}
img{{display:block;width:100%;max-height:85vh;object-fit:contain}}a{{color:#126b7d}}h2{{font-size:20px}}
table{{border-collapse:collapse;width:100%;max-width:700px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dfe7eb}}
</style><h1>Province map / seed {config.seed}</h1>
<p>{grid.count:,} hexes · {len(targets)} connected provinces · {report['changed_hex_count']:,} hexes cleaned<br>
Neighbors: min {degree['min']} / max {degree['max']} / mean {degree['mean']:.2f} / modes {degree['modes']}<br>
Classic degree similarity: {report['classic_degree_similarity_score']:.1f}/100 (structural diagnostic, not gameplay balance)</p>
<p><a href="report.json">Statistics</a> · <a href="parameters.json">Parameters</a> · <a href="map.json">Map data</a><br>
Terrain views: blue = water (lighter is shallower), green = land (darker is higher). Cleaned cells keep original elevation data but adopt their new terrain color.</p>{score_panel}{shape_panel}{cards}</html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    progress(f'Done in {report["elapsed_seconds"]:.2f}s: {output.resolve()}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='JSON parameter file')
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--open', action='store_true', help='Open HTML preview after generation')
    defaults = Config()
    for field in fields(defaults):
        if field.name == 'wrap_x':
            parser.add_argument('--wrap-x', action=argparse.BooleanOptionalAction, default=None)
        else:
            parser.add_argument('--' + field.name.replace('_', '-'), type=type(getattr(defaults, field.name)))
    args = parser.parse_args()
    try:
        settings = json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
        settings.update({f.name: getattr(args, f.name) for f in fields(defaults) if getattr(args, f.name) is not None})
        generate(Config(**settings), args.output)
    except (ValueError, TypeError, OSError) as error:
        parser.exit(2, f'Error: {error}\n')
    if args.open:
        import webbrowser
        webbrowser.open((args.output / 'index.html').resolve().as_uri())


if __name__ == '__main__':
    main()
