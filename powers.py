"""Symmetric regional starts on the generated movement graph; no convoy shortcuts."""
from collections import deque
from itertools import combinations
import random


def movement_graphs(provinces, movement):
    land = {str(p['id']) for p in provinces if p['terrain'] == 'land' and not p.get('impassable')}
    locations = {p['name']: p for p in movement['locations']}
    water = set(locations) - land
    coastal = {p for p in land if set(locations[p]['neighbors']) & water}
    army = {p: set(locations[p]['neighbors']) & land for p in land}
    fleet = {}
    for p in water | coastal:
        fleet[p] = {n for n in locations[p]['neighbors'] if n in water | coastal
                    and (p in water or n in water or
                         set(locations[p]['neighbors']) & set(locations[n]['neighbors']) & water)}
    return {'army': army, 'fleet': fleet}


def paths_from(graph, start, limit=2):
    if start not in graph:
        return {}
    paths = {start: [start]}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if len(paths[current]) > limit:
            continue
        for neighbor in sorted(graph[current]):
            if neighbor not in paths:
                paths[neighbor] = paths[current] + [neighbor]
                queue.append(neighbor)
    return paths


def assign_powers(provinces, movement, config):
    for p in provinces:
        p.update(owner=None, home_power=None, core=None, half_core=None)
    centers = sorted(p['id'] for p in provinces if p.get('supply_center') and not p.get('impassable'))
    victory = len(centers) // 2 + 1
    result = {'mode': 'asymmetric' if config.asymmetric else 'symmetric', 'status': 'unavailable',
              'seed': config.power_seed, 'players': [], 'victory_count': victory,
              'victory_conditions': 'classic', 'starting_centers_per_player': 3,
              'neutral_center_ids': centers,
              'rule': 'Each power must have at least one coastal starting SC. From each starting SC, one unit type (army or fleet) can reach both other SCs in at most two moves. No convoys; occupancy ignored.',
              'movement_note': 'Uses generated unsplit coastal provinces. Direct coastal fleet edges require a shared neighboring sea. Split-coast adjudicator export is not implemented.',
              'message': ''}
    if config.asymmetric:
        result.update(status='not_implemented', victory_count=None, victory_conditions=None,
                      starting_centers_per_player=None, message='Asymmetric power allocation: to be implemented. Province capacity and SC budget include the 1.5x factor.')
        return result
    if not config.sc_enabled:
        result['message'] = 'Enable supply centers to assign symmetric powers.'
        return result
    if len(centers) < 3 * config.players:
        result['message'] = f'Symmetric powers need {3 * config.players} SCs; only {len(centers)} exist. Increase province count or richness.'
        return result
    if victory <= 3:
        result['message'] = 'This SC budget would meet the majority victory condition at the start. Increase province count or richness.'
        return result
    graphs = movement_graphs(provinces, movement)
    coastal_centers = {pid for pid in centers if str(pid) in graphs['fleet']}
    if len(coastal_centers) < config.players:
        result['message'] = f'Each power needs a coastal starting SC; only {len(coastal_centers)} coastal SCs exist for {config.players} powers. Rerun SCs or increase coastal preference.'
        return result
    routes = {pid: {kind: paths_from(graph, str(pid)) for kind, graph in graphs.items()} for pid in centers}
    # Enumerate local triples rather than all C(total SCs, 3) combinations.
    candidates = {}
    for anchor in centers:
        nearby = sorted({int(n) for paths in routes[anchor].values() for n in paths
                         if n.isdigit() and int(n) in centers and int(n) > anchor})
        for pair in combinations(nearby, 2):
            triple = (anchor, *pair)
            if not coastal_centers.intersection(triple):
                continue
            witnesses = {}
            for origin in triple:
                others = [str(p) for p in triple if p != origin]
                feasible = [(kind, paths) for kind, paths in routes[origin].items() if all(n in paths for n in others)]
                if not feasible:
                    break
                kind, paths = min(feasible, key=lambda item: sum(len(item[1][n]) for n in others))
                witnesses[str(origin)] = {'unit_type': kind, 'routes': {n: paths[n] for n in others}}
            if len(witnesses) == 3:
                candidates[triple] = witnesses
    if not candidates:
        result['message'] = 'No three-center group meets both the coastal-start and two-move rules. Rerun SCs or adjust their distribution.'
        return result
    # Select disjoint triples as complete assignments. Prefer spacing between powers,
    # comparable nearby neutral access, and short routes within each power.
    generic = {p['name']: set(p['neighbors']) for p in movement['locations']}
    distances = {p: {n: len(path)-1 for n, path in paths_from(generic, str(p), len(generic)).items()} for p in centers}
    rng = random.Random(config.power_seed)
    choices = sorted(candidates)
    best = None
    for _ in range(160):
        picked, used = [], set()
        while len(picked) < config.players:
            available = [c for c in choices if not used.intersection(c)]
            if not available:
                break
            def preference(c):
                separation = min((distances[a].get(str(b), len(generic)) for a in c for b in used), default=3)
                internal = sum(len(path)-1 for w in candidates[c].values() for path in w['routes'].values())
                return min(separation, 5) - internal * .08 + rng.random() * 3
            group = max(available, key=preference)
            picked.append(group)
            used.update(group)
        if len(picked) != config.players:
            continue
        neutral = set(centers) - used
        access = [sum(1 / (1 + min(distances[a].get(str(n), len(generic)) for a in group)) for n in neutral) for group in picked]
        separation = min((distances[a].get(str(b), len(generic)) for i, group in enumerate(picked)
                          for other in picked[i+1:] for a in group for b in other), default=3)
        score = min(separation, 4) + min(access) - (max(access)-min(access))
        if best is None or score > best[0]:
            best = (score, picked, access)
    if best is None:
        result['message'] = f'Could not find {config.players} disjoint three-center groups satisfying the coastal-start and two-move rules. Rerun SCs or change their distribution; no partial powers were assigned.'
        return result
    _, picked, access = best
    lookup = {p['id']: p for p in provinces}
    for index, group in enumerate(picked):
        name = f'P{index+1}'
        color = f'hsl({round(index * 137.508) % 360},60%,70%)'
        for pid in group:
            lookup[pid].update(owner=name, home_power=name, core=name)
        result['players'].append({'id': name, 'name': name, 'type': 'regional', 'color': color,
                                  'iscc': 3, 'vscc': victory, 'starting_centers': list(group),
                                  'coastal_starting_centers': sorted(coastal_centers.intersection(group)),
                                  'core_province_ids': list(group), 'precore_province_ids': [],
                                  'two_step_routes': candidates[group], 'neutral_access_heuristic': access[index]})
    result.update(status='complete', neutral_center_ids=sorted(set(centers)-set(p for g in picked for p in g)),
                  message=f'{config.players} regional powers, 3 starting home centers each. Victory: {victory} of {len(centers)} SCs. Every power has a coastal starting center and passes the two-move rule. Starting units are not assigned.',
                  balance_note='Assignment heuristic only; neutral access uses the untyped movement graph and does not prove playable opening balance.')
    return result
