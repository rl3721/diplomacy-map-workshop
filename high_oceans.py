"""High oceans: shared geography, separately adjudicated one-unit locations."""


def build_high_oceans(provinces):
    by_id = {p['id']: p for p in provinces}
    deep = {p['id'] for p in provinces if p['terrain'] == 'water'
            and p['neighbors'] and all(by_id[n]['terrain'] == 'water' for n in p['neighbors'])}
    pending = set(deep)
    groups = []
    while pending:
        start = min(pending)
        pending.remove(start)
        group, stack = {start}, [start]
        while stack:
            for neighbor in by_id[stack.pop()]['neighbors']:
                if neighbor in pending:
                    pending.remove(neighbor)
                    group.add(neighbor)
                    stack.append(neighbor)
        if len(group) > 1:
            groups.append(sorted(group))
    region_of = {pid: pid for pid in by_id}
    oceans = []
    for members in groups:
        region = members[0]
        for pid in members:
            region_of[pid] = region
        oceans.append({'id': region, 'name': f'High Ocean {region}',
                       'member_province_ids': members})
    geographical = {}
    for pid, p in by_id.items():
        region = region_of[pid]
        geographical.setdefault(region, set()).update(region_of[n] for n in p['neighbors']
                                                      if region_of[n] != region)
    members_by_region = {}
    for pid, region in region_of.items():
        members_by_region.setdefault(region, []).append(pid)
    slots_by_region = {r: [str(r)] for r in geographical}
    for ocean in oceans:
        region = ocean['id']
        ocean['external_neighbor_count'] = len(geographical[region])
        ocean['capacity'] = min(len(ocean['member_province_ids']),
                                (len(geographical[region]) + 1) // 2, 6)
        ocean['slots'] = [f'{region}.{i}' for i in range(1, ocean['capacity'] + 1)]
        slots_by_region[region] = ocean['slots']
    locations = []
    for region in sorted(geographical):
        for index, name in enumerate(slots_by_region[region]):
            members = members_by_region[region]
            neighbors = {n for r in geographical[region] for n in slots_by_region[r]}
            neighbors.update(n for n in slots_by_region[region] if n != name)
            locations.append({'name': name,
                              'source_province_ids': members,
                              'region_id': region, 'terrain': by_id[region]['terrain'],
                              'capacity': 1, 'neighbors': sorted(neighbors)})
    return {'rules': 'Named slots; no automatic vacancy allocation. Each slot shares all external exits and connects to every sibling slot.',
            'oceans': oceans, 'locations': locations,
            'regions': [{'id': r, 'neighbors': sorted(ns), 'member_province_ids': members_by_region[r]}
                        for r, ns in sorted(geographical.items())],
            'region_of': region_of,
            'zero_capacity_region_ids': [o['id'] for o in oceans if o['capacity'] == 0],
            'capacity_rule': 'min(source province count, ceil(external region neighbors / 2), 6)',
            'one_neighbor_region_ids': sorted(r for r, ns in geographical.items() if len(ns) == 1)}
