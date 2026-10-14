"""Stable display codes; numeric province and movement IDs remain unchanged."""
import random
import string


def assign_names(provinces, movement, seed, water_classes=None):
    by_id = {p['id']: p for p in provinces}
    rng = random.Random(f'{seed}:province-names-v1')
    alphabet = string.ascii_uppercase
    used = set()

    def code(prefix='', suffix=''):
        count = 4 - len(prefix) - len(suffix)
        # Visit a random permutation of the namespace without retry exhaustion.
        space = 26 ** count
        start = rng.randrange(space)
        stride = rng.choice([i for i in range(1, 26) if i % 2 and i != 13])
        for offset in range(space):
            value = (start + offset * stride) % space
            letters = ''
            for _ in range(count):
                letters = alphabet[value % 26] + letters
                value //= 26
            name = prefix + letters + suffix
            if name not in used:
                used.add(name)
                return name
        raise ValueError('Four-letter province name space exhausted; reduce province count.')

    pending = {p['id'] for p in provinces if p['terrain'] == 'land'}
    continents = []
    while pending:
        root = min(pending)
        pending.remove(root)
        members, stack = [root], [root]
        while stack:
            for neighbor in sorted(by_id[stack.pop()]['neighbors']):
                if neighbor in pending:
                    pending.remove(neighbor)
                    members.append(neighbor)
                    stack.append(neighbor)
        continents.append(sorted(members))
    # Largest landmass is A, then B, etc.; islands also count as landmasses.
    continents.sort(key=lambda ids: (-sum(by_id[i]['hex_count'] for i in ids), ids[0]))
    for index, members in enumerate(continents):
        prefix = alphabet[index % 26]
        for pid in members:
            by_id[pid].update(name=code(prefix=prefix), continent_id=index + 1,
                              continent_prefix=prefix)
    for pid, province in sorted(by_id.items()):
        if province['terrain'] == 'water':
            region = movement['region_of'][pid]
            classification = (water_classes or {}).get(region, {'kind': 'sea', 'reason': 'No cell geometry supplied'})
            kind = classification['kind']
            prefix, suffix = {'ocean': ('', 'O'), 'sea': ('', 'S'),
                              'gulf': ('GO', ''), 'strait': ('SO', '')}[kind]
            province.update(name=code(prefix=prefix, suffix=suffix), water_kind=kind,
                            water_classification=dict(classification))
    for region in movement['regions']:
        region['display_name'] = by_id[region['id']]['name']
        if by_id[region['id']]['terrain'] == 'water':
            region['water_classification'] = dict(by_id[region['id']]['water_classification'])
    for ocean in movement['oceans']:
        ocean['display_name'] = by_id[ocean['id']]['name']
    for location in movement['locations']:
        suffix = '.' + location['name'].split('.', 1)[1] if '.' in location['name'] else ''
        location['display_name'] = by_id[location['region_id']]['name'] + suffix
    location_names = {p['name']: p['display_name'] for p in movement['locations']}
    for location in movement['locations']:
        location['neighbor_display_names'] = [location_names[n] for n in location['neighbors']]
    return {'version': 2, 'water_rule': 'Native-cell geometry: Strait SOxx, Gulf GOxx, Ocean xxxO, Sea xxxS; merged high oceans are Ocean.',
            'continent_count': len(continents), 'prefix_reuse': len(continents) > 26}
