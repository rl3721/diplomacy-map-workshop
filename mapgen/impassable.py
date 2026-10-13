"""Select highest mean-elevation land provinces and remove movement access."""
import math


def apply_impassable(provinces, owners, heights, graph, enabled=True, ratio=.02):
    sums = {p['id']: [0., 0] for p in provinces}
    for owner, height in zip(owners, heights):
        sums[owner + 1][0] += height
        sums[owner + 1][1] += 1
    for p in provinces:
        total, count = sums[p['id']]
        p['mean_elevation'] = total / count
    land = sorted((p for p in provinces if p['terrain'] == 'land'),
                  key=lambda p: (-p['mean_elevation'], p['id']))
    count = math.floor(round(len(land) * ratio, 12)) if enabled else 0
    blocked = {p['id'] for p in land[:count]}
    for p in provinces:
        p['impassable'] = p['id'] in blocked
    graph['locations'] = [p for p in graph['locations'] if p['region_id'] not in blocked]
    names = {p['name'] for p in graph['locations']}
    for p in graph['locations']:
        p['neighbors'] = [n for n in p['neighbors'] if n in names]
    playable = {r['id'] for r in graph['regions']} - blocked
    adjacency = {}
    for r in graph['regions']:
        r['impassable'] = r['id'] in blocked
        r['traversable_neighbors'] = sorted(set(r['neighbors']) & playable) if not r['impassable'] else []
        if not r['impassable']:
            adjacency[r['id']] = r['traversable_neighbors']
    reached = set()
    stack = [min(playable)] if playable else []
    while stack:
        p = stack.pop()
        if p not in reached:
            reached.add(p)
            stack.extend(adjacency[p])
    low = sorted(p for p, ns in adjacency.items() if len(ns) < 2) if len(playable) > 1 else []
    two = sorted(p for p, ns in adjacency.items() if len(ns) == 2)
    return {'enabled': enabled, 'ratio': ratio, 'count': count,
            'province_ids': sorted(blocked), 'ranking': 'Mean cell elevation, descending; ties by province ID',
            'rounding': 'floor(land province count * ratio)',
            'legal': bool(playable) and reached == playable and not low,
            'unreachable_region_ids': sorted(playable - reached), 'low_degree_region_ids': low,
            'two_neighbor_penalty_points': 20 * len(two) / len(playable) if playable else 0}
