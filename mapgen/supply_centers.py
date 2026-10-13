"""Seeded, unassigned supply centers scored independently of province layout."""
from collections import deque
from dataclasses import replace
import math
import random
from .profiles import targets_for


BASE_CENTERS_PER_PLAYER = 5.2


def center_budget(config):
    """Fixed SC base scaled by the actual source-province ratio, then rounded once."""
    base_provinces = targets_for(replace(config, province_count=0, size_ratio=1.0, asymmetric=False))['province_count']
    provinces = targets_for(config)['province_count']
    ratio = provinces / base_provinces
    raw = BASE_CENTERS_PER_PLAYER * config.players * ratio * config.sc_richness
    return {'base_per_player': BASE_CENTERS_PER_PLAYER, 'players': config.players,
            'base_province_count': base_provinces, 'source_province_count': provinces,
            'province_ratio': ratio, 'capacity_factor': 1.5 if config.asymmetric else 1.0, 'richness': config.sc_richness, 'unrounded_count': raw,
            'count': math.floor(round(raw, 12) + .5) if config.sc_enabled else 0,
            'rounding': 'nearest integer; halves rounded up',
            'formula': '5.2 * players * (source province count / base province count) * richness'}


def designate(provinces, movement, config):
    for p in provinces:
        p['supply_center'] = False
        p['home_power'] = None
        p['owner'] = None
    eligible = {p['id']: p for p in provinces if p['terrain'] == 'land' and not p.get('impassable')}
    budget = center_budget(config)
    count = budget['count']
    if count > len(eligible):
        raise ValueError(f'Supply-center budget {count} exceeds {len(eligible)} eligible land provinces. '
                         'Reduce richness, increase the land province share, or disable supply centers.')
    result = {'enabled': config.sc_enabled, 'count': count, 'eligible_count': len(eligible),
              'budget': budget,
              'assignment': 'unassigned', 'seed': config.sc_seed, 'province_ids': [],
              'score': None, 'candidate_scores': [],
              'note': 'Placement quality only; player balance requires future power assignment. '
                      'Land spacing never traverses water. Naval access is a sea-route heuristic, not convoy orders.'}
    if not count:
        return result
    adjacency = {pid: sorted(set(p['neighbors']) & eligible.keys()) for pid, p in eligible.items()}
    remaining = set(eligible)
    regions = []
    while remaining:
        stack = [min(remaining)]
        component = set()
        while stack:
            pid = stack.pop()
            if pid not in remaining:
                continue
            remaining.remove(pid)
            component.add(pid)
            stack.extend(adjacency[pid])
        regions.append(sorted(component))
    region_of = {pid: i for i, region in enumerate(regions) for pid in region}
    distances = {}
    for start in eligible:
        distance = {start: 0}
        queue = deque([start])
        while queue:
            pid = queue.popleft()
            for n in adjacency[pid]:
                if n not in distance:
                    distance[n] = distance[pid] + 1
                    queue.append(n)
        distances[start] = distance
    # Water-only paths between coastal provinces, separate from land distances.
    locations = {p['name']: p for p in movement['locations']}
    naval_regions = {i: set() for i in range(len(regions))}
    for pid in eligible:
        start = str(pid)
        visited = {start}
        queue = deque(n for n in locations[start]['neighbors'] if locations[n]['terrain'] == 'water')
        while queue:
            name = queue.popleft()
            if name in visited:
                continue
            visited.add(name)
            for n in locations[name]['neighbors']:
                if locations[n]['terrain'] == 'water':
                    if n not in visited:
                        queue.append(n)
                else:
                    other = int(n)
                    if region_of[other] != region_of[pid]:
                        naval_regions[region_of[pid]].add(region_of[other])
    coastal = {pid for pid, p in eligible.items() if p['category'] == 'coastal'}
    coastal_target = min(1., len(coastal) / len(eligible) * config.sc_coastal_preference)
    feasible_coastal_target = max(max(0, count - (len(eligible) - len(coastal))) / count,
                                 min(coastal_target, min(count, len(coastal)) / count))
    ideal_spacing = 1 + 2 * config.sc_distribution * max(0., math.sqrt(len(eligible) / count) - 1)
    regional_targets = [count * len(region) / len(eligible) for region in regions]
    accessibility = {}
    for pid in eligible:
        # Available land approaches plus a separately evaluated sea-access bonus.
        sea_access = len(regions) == 1 or bool(naval_regions[region_of[pid]])
        accessibility[pid] = .75 * min(1., len(adjacency[pid]) / 4) + .25 * sea_access

    def evaluate(selected):
        chosen = set(selected)
        nearest = [min((distances[p][q] for q in chosen - {p} if q in distances[p]), default=None)
                   for p in selected]
        spacing_values = [max(0., 1 - abs(d - ideal_spacing) / max(1., ideal_spacing))
                          for d in nearest if d is not None]
        spacing = sum(spacing_values) / len(spacing_values) if spacing_values else 1.
        regional_counts = [sum(p in chosen for p in region) for region in regions]
        regional = max(0., 1 - sum(abs(a-b) for a, b in zip(regional_counts, regional_targets)) / (2*count))
        coast_fraction = len(chosen & coastal) / count
        composition = max(0., 1 - abs(coast_fraction - feasible_coastal_target))
        access = sum(accessibility[p] for p in selected) / count
        parts = {'spacing': spacing * 100, 'regional_distribution': regional * 100,
                 'coastal_mix': composition * 100, 'accessibility': access * 100}
        score = .4 * parts['spacing'] + .3 * parts['regional_distribution'] + .2 * parts['coastal_mix'] + .1 * parts['accessibility']
        return score, parts, regional_counts

    rng = random.Random(config.sc_seed)
    best = None
    scores = []
    for _ in range(config.sc_iterations):
        quotas = [math.floor(t) for t in regional_targets]
        # Weighted randomized rounding: small islands have a chance, not a guaranteed SC.
        fractions = [t - q for t, q in zip(regional_targets, quotas)]
        for _ in range(count - sum(quotas)):
            choices = [i for i in range(len(regions)) if fractions[i] > 0]
            i = rng.choices(choices, weights=[fractions[i] for i in choices])[0]
            quotas[i] += 1
            fractions[i] = 0
        selected = []
        for region, quota in zip(regions, quotas):
            local = []
            for _ in range(quota):
                options = [p for p in region if p not in local]
                def priority(p):
                    near = min((distances[p][q] for q in local), default=ideal_spacing)
                    spacing = -abs(near - ideal_spacing) / max(1., ideal_spacing)
                    coast_need = feasible_coastal_target * (len(selected) + 1) - sum(q in coastal for q in selected)
                    return spacing + .7 * (coast_need if p in coastal else -coast_need) + .2 * accessibility[p] + rng.random() * .8
                chosen = max(options, key=priority)
                local.append(chosen)
                selected.append(chosen)
        score, parts, actual = evaluate(selected)
        scores.append(score)
        if best is None or score > best[0]:
            best = score, sorted(selected), parts, actual
    score, selected, parts, actual = best
    for pid in selected:
        eligible[pid]['supply_center'] = True
    result.update(province_ids=selected, score=score, components=parts, candidate_scores=scores,
                  weights={'spacing': .4, 'regional_distribution': .3, 'coastal_mix': .2, 'accessibility': .1},
                  coastal_target=coastal_target, feasible_coastal_target=feasible_coastal_target,
                  actual_coastal_count=len(set(selected) & coastal), target_nearest_land_distance=ideal_spacing,
                  regions=[{'province_ids': r, 'expected_centers': regional_targets[i], 'actual_centers': actual[i],
                            'naval_reachable_region_indices': sorted(naval_regions[i])} for i, r in enumerate(regions)])
    return result
