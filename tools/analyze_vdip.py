"""Reproduce a six-variant structural comparison from public vDiplomacy sources.

Run from the project root: python research/analyze_vdip.py [--download]
PHP is parsed as data and is never executed. Sources are pinned to one revision.
"""
import argparse
from collections import Counter, deque
import csv
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import sys
import urllib.request

from mapgen.generator import summary
from mapgen.scoring import graph_metrics, graph_views

ROOT = Path(__file__).resolve().parents[1] / 'research'
REVISION = '72c81f0dd73bedccc11f13a750dfcc62f580549a'
# Totals cross-checked against vDiplomacy variant pages (Land means inland).
VARIANTS = {
    'Classic': (1, 'regional', (14, 42, 19)),
    'AncMed': (9, 'regional', (14, 45, 20)),
    'Modern2': (19, 'regional', (30, 78, 33)),
    'GobbleEarth': (96, 'global', (40, 150, 54)),
    'Imperial2': (81, 'wraparound', (81, 178, 87)),
    'WWIV': (52, 'wraparound', (164, 252, 97)),
}


def download():
    for variant in VARIANTS:
        folder = ROOT / 'vdip_sources' / variant
        folder.mkdir(parents=True, exist_ok=True)
        url = f'https://api.github.com/repos/Sleepcap/vDiplomacy/contents/variants/{variant}?ref={REVISION}'
        with urllib.request.urlopen(url, timeout=30) as response:
            entries = json.load(response)
        blobs = {entry['name']: entry['sha'] for entry in entries}
        for name in ('install.php', 'variant.php', 'rules.html'):
            if variant == 'Classic' and name == 'rules.html':
                continue
            path = folder / name
            def matches(content):
                return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest() == blobs[name]
            if path.exists() and matches(path.read_bytes()):
                continue
            url = f'https://raw.githubusercontent.com/Sleepcap/vDiplomacy/{REVISION}/variants/{variant}/{name}'
            for suffix in ('', '?download=1'):
                with urllib.request.urlopen(url + suffix, timeout=30) as response:
                    try:
                        content = response.read()
                    except http.client.IncompleteRead as error:
                        content = error.partial
                if matches(content):
                    path.write_bytes(content)
                    break
            else:
                raise ValueError(f'Incomplete or mismatched download: {variant}/{name}')
        (folder / 'revision_verification.json').write_text(json.dumps(entries, indent=2), encoding='utf-8')
        print('Verified pinned sources:', variant, flush=True)


def array_rows(text, variable):
    match = re.search(r'\$' + variable + r'\s*=\s*array\((.*?)\n\);', text, re.S)
    if not match:
        raise ValueError(f'Missing array {variable}')
    rows = []
    for line in match[1].splitlines():
        if not line.strip() or line.lstrip().startswith('//'):
            continue
        row = re.fullmatch(r'\s*array\((.*)\)\s*,?\s*', line)
        if not row:
            raise ValueError(f'Unparsed source row: {line}')
        # Only string values are needed: province names/types and permission flags.
        strings = re.findall(r"'((?:\\.|[^'\\])*)'", row[1])
        rows.append([s.replace("\\'", "'").replace('\\\\', '\\') for s in strings])
    return rows


def parse_variant(variant):
    folder = ROOT / 'vdip_sources' / variant
    text = (folder / 'install.php').read_text(encoding='utf-8-sig')
    info = (folder / 'variant.php').read_text(encoding='utf-8-sig')
    name = re.search(r"\$fullName\s*=\s*'([^']+)'", info)[1]
    territories = array_rows(text, 'territoryRawData')
    borders = array_rows(text, 'bordersRawData')
    names = {row[0] for row in territories}
    assert len(names) == len(territories), 'Duplicate source province name'
    parents = {name: re.sub(r' \([^()]+ Coast\)$', '', name) for name in names}
    assert all(parent in names for parent in parents.values()), 'Unresolved coast parent'
    types = {row[0]: row[1] for row in territories if parents[row[0]] == row[0]}
    assert set(types.values()) <= {'Land', 'Coast', 'Sea'}
    graph = {name: set() for name in types}
    army = {name: set() for name in types if types[name] != 'Sea'}
    source_warnings = []
    duplicate_borders, raw_edges = 0, set()
    for row in borders:
        assert len(row) == 4, row
        first, second, fleets, armies = row
        assert first in names and second in names
        assert fleets in ('Yes', 'No') and armies in ('Yes', 'No')
        a, b = parents[first], parents[second]
        if fleets == 'Yes' or armies == 'Yes':
            if a == b:
                continue
            edge = tuple(sorted((a, b)))
            duplicate_borders += edge in raw_edges
            raw_edges.add(edge)
            graph[a].add(b)
            graph[b].add(a)
        if armies == 'Yes':
            if a not in army or b not in army:
                source_warnings.append(f'Army permission involving a sea province: {a} / {b}; '
                                       'retained in union graph, excluded from land-only army graph.')
            else:
                army[a].add(b)
                army[b].add(a)
    provinces = []
    mismatch = []
    for name in sorted(types):
        terrain = 'water' if types[name] == 'Sea' else 'land'
        category = 'sea' if terrain == 'water' else ('coastal' if any(types[n] == 'Sea' for n in graph[name]) else 'inland')
        declared = {'Sea': 'sea', 'Coast': 'coastal', 'Land': 'inland'}[types[name]]
        if category != declared:
            mismatch.append({'name': name, 'declared': declared, 'sea_adjacency_category': category})
        provinces.append({'id': name, 'terrain': terrain, 'category': category,
                          'declared_category': declared, 'neighbors': sorted(graph[name])})
    counts = Counter(types.values())
    expected = VARIANTS[variant][2]
    assert tuple(counts[k] for k in ('Land', 'Coast', 'Sea')) == expected, (variant, counts, expected)
    stats = {key: graph_metrics(view, source_limit=len(view)) for key, view in graph_views(provinces).items()}
    n = len(provinces)
    degrees = [len(p['neighbors']) for p in provinces]
    # Independent BFS using frontier sets checks the mean path and diameter from scoring.py.
    total_distance = pair_count = diameter = 0
    for start in graph:
        visited, frontier, depth = {start}, {start}, 0
        while frontier:
            frontier = set().union(*(graph[node] for node in frontier)) - visited
            depth += 1
            total_distance += len(frontier) * depth
            pair_count += len(frontier)
            if frontier:
                diameter = max(diameter, depth)
            visited.update(frontier)
    assert abs(stats['all']['mean_path_hops'] - total_distance / pair_count) < 1e-12
    assert sum(degrees) == 2 * stats['all']['edge_count']
    return {
        'variant': variant, 'name': re.search(r"\$fullName\s*=\s*'([^']+)'", info)[1],
        'topology_label': VARIANTS[variant][1], 'province_count': n,
        'declared_counts': dict(counts), 'declared_fractions': {k: counts[k] / n for k in ('Land', 'Coast', 'Sea')},
        'degree': summary(degrees),
        'degree_by_declared_category': {k: summary([len(p['neighbors']) for p in provinces if types[p['id']] == k])
                                         for k in ('Land', 'Coast', 'Sea')},
        'graph_metrics': stats, 'diameter': diameter,
        'normalized_mean_path': stats['all']['mean_path_hops'] / math.sqrt(n),
        'degree_at_most_3_fraction': sum(d <= 3 for d in degrees) / n,
        'army_graph_components': graph_metrics(army, source_limit=1)['component_sizes'],
        'category_mismatches': mismatch, 'provinces': provinces,
        'source_warnings': source_warnings,
        'source_rows': {'territories_including_coasts': len(territories), 'borders': len(borders),
                        'coast_rows_collapsed': len(territories) - n, 'duplicate_collapsed_edges': duplicate_borders},
        'source_url': f'https://github.com/Sleepcap/vDiplomacy/blob/{REVISION}/variants/{variant}/install.php',
        'variant_url': f'https://www.vdiplomacy.com/variants.php?variantID={VARIANTS[variant][0]}',
        'source_sha256': hashlib.sha256((folder / 'install.php').read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    if args.download:
        download()
    results = [parse_variant(variant) for variant in VARIANTS]
    artifact = {'source_revision': REVISION, 'scope': 'Six deliberately selected variants, not a site-wide census.',
                'method': 'Static undirected union of army/fleet border permissions, coast children collapsed. '
                          'Dynamic rule-dependent connections are excluded. All-source BFS (no sampling). '
                          'Declared Coast can include river-access provinces without direct sea adjacency.',
                'variants': results}
    (ROOT / 'variant_statistics.json').write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    rows = []
    for r in results:
        metric = r['graph_metrics']['all']
        row = {'variant': r['name'], 'topology': r['topology_label'], 'provinces': r['province_count'],
               **{k.lower(): r['declared_counts'][k] for k in ('Land', 'Coast', 'Sea')},
               'min_degree': r['degree']['min'], 'max_degree': r['degree']['max'],
               'mode_degree': '/'.join(map(str, r['degree']['modes'])), 'mean_degree': r['degree']['mean'],
               'edges': metric['edge_count'], 'mean_path': metric['mean_path_hops'],
               'normalized_mean_path': r['normalized_mean_path'], 'diameter': r['diameter'],
               'articulation_points': metric['articulation_count'], 'bridges': metric['bridge_count'],
               'land_components': len(r['graph_metrics']['land']['component_sizes']),
               'sea_components': len(r['graph_metrics']['sea']['component_sizes']),
               'source': r['source_url']}
        rows.append(row)
        print(json.dumps(row))
        if r['category_mismatches']:
            print('CATEGORY DIFFERENCES', r['variant'], json.dumps(r['category_mismatches']))
    with (ROOT / 'variant_statistics.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
