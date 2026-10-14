"""Topology-aware, cell-scale heuristics for geographical water labels."""
from collections import defaultdict, deque
import math
import statistics


def groups(cells, neighbors):
    pending = set(cells)
    result = []
    while pending:
        start = min(pending)
        pending.remove(start)
        component, stack = {start}, [start]
        while stack:
            for nb in neighbors[stack.pop()]:
                if nb in pending:
                    pending.remove(nb)
                    component.add(nb)
                    stack.append(nb)
        result.append(component)
    return result


def eligible(features, kind, require_wider=True):
    if features.get('high_ocean', False):
        return False
    if kind == 'strait':
        return features['mouth_count'] == 2 and features['bank_count'] >= 2 and (not require_wider or features['wider_mouth_count'] == 2)
    if kind == 'gulf':
        return features['mouth_count'] == 1 and features['coast_fraction'] >= .6 and features['wider_mouth_count'] >= 1
    raise ValueError('Unknown water kind')


def kind_from_features(features, strait_width_max=.65, gulf_mouth_depth_max=1.0, strait_require_wider=True):
    if features.get('high_ocean', False):
        return 'ocean', 'Merged high ocean'
    if eligible(features, 'strait', strait_require_wider) and features['width_ratio'] <= strait_width_max:
        return 'strait', ('Narrow water between separate banks with two mouths reaching wider water' if strait_require_wider
                          else 'Exploratory: narrow water between separate banks and two mouths; wider-water check disabled')
    if (eligible(features, 'gulf') and features['mouth_depth_ratio'] <= gulf_mouth_depth_max):
        return 'gulf', 'Coast-enclosed water with one mouth narrower than the configured interior-width limit'
    if features['coast_fraction'] == 0 or (features['coast_fraction'] <= .2 and features['width_ratio'] / 2 >= .35):
        return 'ocean', 'Open water with low coastal enclosure'
    return 'sea', 'Coastal, enclosed or ambiguous water; fallback classification'


def classify_water(grid, land, owners, movement, strait_width_max=.65, gulf_mouth_depth_max=1.0):
    """Measure native graph geometry, never distances in the SVG projection.

    Boundary contacts approximate lengths on the cell mesh. Widths are graph
    distances, scaled by typical water-province area. These are heuristic names,
    not changes to movement rules or a claim of geological classification.
    """
    neighbors = grid.neighbors
    region_of = movement['region_of']
    cells = defaultdict(set)
    for cell, pid in enumerate(owners):
        if not land[cell]:
            cells[region_of[pid + 1]].add(cell)
    if not cells:
        return {}
    source_sizes = defaultdict(int)
    for cell, pid in enumerate(owners):
        if not land[cell]:
            source_sizes[pid] += 1
    scale = math.sqrt(statistics.mean(source_sizes.values()))
    # Multi-source distance from coastline, with topology seam edges intact.
    distance = {}
    queue = deque()
    for cell in range(grid.count):
        if not land[cell] and any(land[n] for n in neighbors[cell]):
            distance[cell] = 1
            queue.append(cell)
    while queue:
        cell = queue.popleft()
        for nb in neighbors[cell]:
            if not land[nb] and nb not in distance:
                distance[nb] = distance[cell] + 1
                queue.append(nb)
    high = {o['id'] for o in movement['oceans']}
    result = {}
    for region, members in sorted(cells.items()):
        coast, exits = defaultdict(int), defaultdict(int)
        for cell in members:
            for nb in neighbors[cell]:
                if land[nb]:
                    coast[nb] += 1
                elif nb not in members:
                    exits[nb] += 1
        shore = sum(coast.values())
        opening = sum(exits.values())
        fraction = shore / max(1, shore + opening)
        mouth_groups = groups(exits, neighbors)
        # Ignore pinhole exits when measuring the main mouths.
        mouths = [g for g in mouth_groups if sum(exits[n] for n in g) >= max(1, opening * .15)]
        banks = groups(coast, neighbors)
        depth = max((distance.get(c, scale) for c in members), default=0)
        width_ratio = 2 * depth / scale
        # Verify each mouth reaches substantial, wider water outside the region.
        # Bounded local searches avoid repeatedly flooding the entire ocean.
        wider = []
        probe_limit = max(8, math.ceil(scale * scale * .5))
        for mouth in mouths:
            seen = set(mouth)
            frontier = deque(sorted(mouth))
            while frontier and len(seen) < probe_limit:
                cell = frontier.popleft()
                for nb in neighbors[cell]:
                    if not land[nb] and nb not in members and nb not in seen:
                        seen.add(nb)
                        frontier.append(nb)
            wider.append(len(seen) >= max(4, scale * scale * .15)
                         and max((distance.get(c, scale) for c in seen), default=0) > depth * 1.25)
        mouth_width = max((sum(exits[n] for n in g) for g in mouths), default=0)
        features = {'high_ocean': region in high, 'coast_fraction': fraction,
                          'mouth_count': len(mouths), 'bank_count': len(banks),
                          'width_ratio': width_ratio, 'mouth_width_ratio': mouth_width / scale,
                          'mouth_depth_ratio': mouth_width / max(depth, 1e-12),
                          'wider_mouth_count': sum(wider), 'scale_cells': scale}
        kind, reason = kind_from_features(features, strait_width_max, gulf_mouth_depth_max)
        result[region] = dict(features, kind=kind, reason=reason)
    return result
