"""Size-adaptive structural scores. All scores are diagnostics, not game balance."""
from collections import Counter, deque
from functools import lru_cache
import json
import math
from pathlib import Path
import statistics
from profiles import targets_for, reference_members
from shapes import shape_error as province_shape_error


COMPONENTS = ('degree', 'composition', 'global', 'size', 'shape')


def similarity(distance, tolerance):
    return 100 * max(0.0, 1.0 - distance / tolerance)


def wasserstein(first, second):
    """1D Wasserstein distance between weighted distributions (arbitrary total mass)."""
    if not first or not second:
        return None
    total_a, total_b = sum(first.values()), sum(second.values())
    previous = min(min(first), min(second))
    ca = cb = result = 0.0
    for value in sorted(first.keys() | second.keys()):
        result += abs(ca - cb) * (value - previous)
        ca += first.get(value, 0) / total_a
        cb += second.get(value, 0) / total_b
        previous = value
    return result


def graph_metrics(graph, source_limit=128):
    """Exact components/bottlenecks; deterministic sampled paths above source_limit nodes."""
    nodes = sorted(graph)
    n = len(nodes)
    seen, sizes = set(), []
    for start in nodes:
        if start in seen:
            continue
        seen.add(start)
        component = [start]
        for node in component:
            for nb in graph[node]:
                if nb not in seen:
                    seen.add(nb)
                    component.append(nb)
        sizes.append(len(component))

    # Iterative Tarjan traversal avoids Python recursion limits on long/thin maps.
    discovery, low, parent, children = {}, {}, {}, Counter()
    articulation, bridges = set(), 0
    for start in nodes:
        if start in discovery:
            continue
        discovery[start] = low[start] = len(discovery)
        parent[start] = None
        stack = [(start, iter(sorted(graph[start])))]
        while stack:
            node, neighbors = stack[-1]
            nb = next(neighbors, None)
            if nb is not None:
                if nb not in discovery:
                    parent[nb] = node
                    children[node] += 1
                    discovery[nb] = low[nb] = len(discovery)
                    stack.append((nb, iter(sorted(graph[nb]))))
                elif nb != parent[node]:
                    low[node] = min(low[node], discovery[nb])
            else:
                stack.pop()
                ancestor = parent[node]
                if ancestor is None:
                    if children[node] > 1:
                        articulation.add(node)
                else:
                    low[ancestor] = min(low[ancestor], low[node])
                    if low[node] > discovery[ancestor]:
                        bridges += 1
                    if parent[ancestor] is not None and low[node] >= discovery[ancestor]:
                        articulation.add(ancestor)

    sample_count = min(n, source_limit)
    sources = [nodes[i * n // sample_count] for i in range(sample_count)]
    hops = Counter()
    for start in sources:
        distances = {start: 0}
        pending = deque([start])
        while pending:
            node = pending.popleft()
            for nb in graph[node]:
                if nb not in distances:
                    distances[nb] = distances[node] + 1
                    hops[distances[nb]] += 1
                    pending.append(nb)
    edges = sum(len(v) for v in graph.values()) // 2
    reachable = sum(size * (size - 1) for size in sizes)
    pair_count = n * (n - 1)
    return {
        'node_count': n, 'edge_count': edges, 'component_sizes': sorted(sizes, reverse=True),
        'unreachable_pair_fraction': 1 - reachable / pair_count if pair_count else 0.0,
        'articulation_count': len(articulation), 'articulation_fraction': len(articulation) / n if n else 0,
        'bridge_count': bridges, 'bridge_fraction': bridges / edges if edges else 0,
        'path_source_count': sample_count, 'paths_exact': sample_count == n,
        'path_hop_histogram': dict(sorted(hops.items())),
        'mean_path_hops': sum(k * v for k, v in hops.items()) / sum(hops.values()) if hops else None,
    }


def graph_views(provinces):
    full = {p['id']: set(p['neighbors']) for p in provinces}
    land = {p['id'] for p in provinces if p['terrain'] == 'land'}
    water = set(full) - land
    return {'all': full, 'land': {p: full[p] & land for p in land},
            'sea': {p: full[p] & water for p in water}}


@lru_cache(maxsize=1)
def classic_reference():
    data = json.loads(Path(__file__).with_name('classic_reference.json').read_text(encoding='utf-8'))
    rows = data['provinces']
    land = {p['id'] for p in rows if p['land']}
    provinces = [{'id': p['id'], 'neighbors': p['neighbors'], 'terrain': 'land' if p['land'] else 'water',
                  'category': ('coastal' if any(nb not in land for nb in p['neighbors']) else 'inland')
                  if p['land'] else 'sea'} for p in rows]
    return {'source': data['source'], 'provinces': provinces,
            'graphs': {name: graph_metrics(graph) for name, graph in graph_views(provinces).items()}}


def normalized_paths(metrics):
    scale = math.sqrt(max(1, metrics['node_count']))
    return {float(hops) / scale: count for hops, count in metrics['path_hop_histogram'].items()}


def component_profile(metrics):
    n = metrics['node_count']
    result = Counter()
    for size in metrics['component_sizes']:
        result[size / n] += size
    return result


def compare_graph(actual, reference, config):
    if not actual['node_count']:
        return {'score': 0.0, 'reason': 'Missing graph category', 'metrics': actual}
    actual_paths, reference_paths = normalized_paths(actual), normalized_paths(reference)
    path_distance = wasserstein(actual_paths, reference_paths)
    reference_mean = sum(x * count for x, count in reference_paths.items()) / sum(reference_paths.values())
    relative_path_error = path_distance / reference_mean if path_distance is not None else None
    path_score = similarity(relative_path_error, config.path_tolerance) if relative_path_error is not None else 0.0
    profile_distance = wasserstein(component_profile(actual), component_profile(reference))
    unreachable_error = abs(actual['unreachable_pair_fraction'] - reference['unreachable_pair_fraction'])
    fragmentation_error = (profile_distance + unreachable_error) / 2
    bottleneck_error = (abs(actual['articulation_fraction'] - reference['articulation_fraction'])
                        + abs(actual['bridge_fraction'] - reference['bridge_fraction'])) / 2
    fragmentation_score = similarity(fragmentation_error, config.fragmentation_tolerance)
    bottleneck_score = similarity(bottleneck_error, config.bottleneck_tolerance)
    return {'score': .5 * path_score + .3 * fragmentation_score + .2 * bottleneck_score,
            'path_score': path_score, 'relative_normalized_path_error': relative_path_error,
            'fragmentation_score': fragmentation_score, 'fragmentation_error': fragmentation_error,
            'bottleneck_score': bottleneck_score, 'bottleneck_error': bottleneck_error,
            'metrics': actual}


def combine_scores(component_scores, weights):
    total = sum(weights.values())
    if total <= 0 or any(weight < 0 for weight in weights.values()):
        raise ValueError('Scoring weights must be nonnegative and at least one must be positive')
    details = {name: {'score': component_scores[name], 'weight': weights[name],
                      'normalized_weight': weights[name] / total,
                      'contribution': component_scores[name] * weights[name] / total} for name in weights}
    return {'total': sum(part['contribution'] for part in details.values()), 'components': details}


def score_map(provinces, shape_efficiencies, config):
    target = targets_for(config, len(provinces))
    references = reference_members(target['global_profile'])
    categories = ('inland', 'coastal', 'sea')
    n = len(provinces)
    counts = Counter(p['category'] for p in provinces)
    degree_details = {}
    for category in categories:
        actual = Counter(len(p['neighbors']) for p in provinces if p['category'] == category)
        baseline = target['degree_histograms'][category]
        distance = wasserstein(actual, baseline)
        degree_details[category] = {'distance': distance,
                                    'score': similarity(distance, config.degree_tolerance) if distance is not None else 0.0}
    composition_distance = sum(abs(counts[k] / n - target['category_fractions'][k]) for k in categories) / 2
    graphs = {}
    for name, graph in graph_views(provinces).items():
        metrics = graph_metrics(graph)
        comparisons = {ref['key']: compare_graph(metrics, ref['graphs'][name], config) for ref in references}
        graphs[name] = {'metrics': metrics, 'score': statistics.mean(c['score'] for c in comparisons.values()),
                        'comparisons': comparisons}
    size_error = statistics.mean(abs(math.log(p['hex_count'] / p['target_hex_count'])) for p in provinces)
    shape_errors = [province_shape_error(p, value) for p, value in zip(provinces, shape_efficiencies)]
    worst_count = max(1, math.ceil(n * .1))
    mean_shape_error = statistics.mean(shape_errors)
    worst_shape_error = statistics.mean(sorted(shape_errors, reverse=True)[:worst_count])
    shape_error = .5 * mean_shape_error + .5 * worst_shape_error
    scores = {'degree': statistics.mean(d['score'] for d in degree_details.values()),
              'composition': similarity(composition_distance, config.composition_tolerance),
              'global': statistics.mean(g['score'] for g in graphs.values()),
              'size': similarity(size_error, config.size_tolerance),
              'shape': similarity(shape_error, config.shape_tolerance)}
    combined = combine_scores(scores, {k: getattr(config, 'weight_' + k) for k in COMPONENTS})
    combined.update({
        'version': 3, 'reference_source': target['sources'], 'targets': target,
        'warnings': ['Small province counts give coarse proportions and unstable distributions.'] if n < 30 else [],
        'scaling': 'Category proportions; conditional degree distributions; path hops / sqrt(graph node count); '
                   'component area fractions; bottleneck rates; relative size errors; perimeter efficiency.',
        'degree': degree_details,
        'composition': {'total_variation_distance': composition_distance,
                        'actual_counts': {k: counts[k] for k in categories},
                        'actual_fractions': {k: counts[k] / n for k in categories},
                        'target_fractions': target['category_fractions'],
                        'expected_counts': {k: n * target['category_fractions'][k] for k in categories}},
        'global': graphs, 'reference_graphs': {ref['key']: ref['graphs'] for ref in references},
        'size': {'mean_absolute_log_error': size_error},
        'shape': {'mean_perimeter_efficiency': statistics.mean(shape_efficiencies),
                  'min_perimeter_efficiency': min(shape_efficiencies),
                  'worst_decile_perimeter_efficiency': statistics.mean(sorted(shape_efficiencies)[:worst_count]),
                  'mean_shape_error': mean_shape_error, 'worst_decile_shape_error': worst_shape_error,
                  'combined_shape_error': shape_error,
                  'worst_province_ids': [p['id'] for p, e in sorted(zip(provinces, shape_errors), key=lambda pair: pair[1], reverse=True)[:worst_count]],
                  'flagged_province_ids': [p['id'] for p in provinces if p.get('normalized_internal_diameter', 0) > 4.5 or p.get('avoidable_thin_hex_fraction', 0) > .05 or p.get('single_hex_neck_fraction', 0) > .2]},
        'tolerances': {name: getattr(config, name) for name in ('degree_tolerance', 'composition_tolerance',
                       'path_tolerance', 'fragmentation_tolerance', 'bottleneck_tolerance', 'size_tolerance', 'shape_tolerance')},
    })
    if any(not value['metrics']['paths_exact'] for value in graphs.values()):
        combined['warnings'].append('Travel distributions estimated from 128 deterministic source provinces per graph.')
    if n >= 3 and target['mean_degree_target'] > 6 - 12 / n:
        combined['warnings'].append('Requested mean degree exceeds the planar adjacency bound for this province count; connectivity is a soft preference and cannot be matched exactly.')
    return combined
