"""Resolution-normalized province shape diagnostics; all traversal honors wrap."""
import math


def region_shape(cells, owners, terrain, grid, pid):
    graph = {cell: [n for n in grid.neighbors[cell] if owners[n] == pid] for cell in cells}
    n = len(cells)

    def farthest(start):
        distances = {start: 0}
        queue = [start]
        for cell in queue:
            for nb in graph[cell]:
                if nb not in distances:
                    distances[nb] = distances[cell] + 1
                    queue.append(nb)
        endpoint = max(distances, key=lambda cell: (distances[cell], -cell))
        return endpoint, distances[endpoint]

    endpoint, _ = farthest(cells[0])
    _, diameter = farthest(endpoint)
    # Iterative articulation analysis: largest portion cut off by removing one
    # hex, excluding the largest remaining component. No recursion depth limit.
    root = cells[0]
    discovery = {root: 0}
    low, parent, subtree, pieces = {root: 0}, {root: None}, {root: 1}, {}
    stack = [(root, iter(graph[root]))]
    while stack:
        cell, neighbors = stack[-1]
        nb = next(neighbors, None)
        if nb is not None:
            if nb not in discovery:
                discovery[nb] = low[nb] = len(discovery)
                parent[nb], subtree[nb] = cell, 1
                stack.append((nb, iter(graph[nb])))
            elif nb != parent[cell]:
                low[cell] = min(low[cell], discovery[nb])
        else:
            stack.pop()
            ancestor = parent[cell]
            if ancestor is not None:
                subtree[ancestor] += subtree[cell]
                low[ancestor] = min(low[ancestor], low[cell])
                if low[cell] >= discovery[ancestor]:
                    pieces.setdefault(ancestor, []).append(subtree[cell])
    neck = 0
    for parts in pieces.values():
        remainder = n - 1 - sum(parts)
        neck = max(neck, n - 1 - max(parts + [remainder]))

    internal = sum(sum(owners[nb] != pid and terrain[nb] == terrain[cell]
                       for nb in grid.neighbors[cell]) for cell in cells)
    perimeter = sum((len(grid.neighbors[cell]) if grid.topology == 'sphere' else 6) - len(graph[cell]) for cell in cells)
    imposed = perimeter - internal
    weighted = internal + .25 * imposed
    bound = 2 * math.ceil(math.sqrt(12 * n - 3))
    surface = {}
    if grid.topology == 'sphere':
        surface_internal = sum(length for cell in cells for nb, length in grid.edge_lengths[cell].items()
                       if owners[nb] != pid and terrain[nb] == terrain[cell])
        surface_imposed = sum(length for cell in cells for nb, length in grid.edge_lengths[cell].items()
                      if owners[nb] != pid and terrain[nb] != terrain[cell])
        weighted = surface_internal + .25 * surface_imposed
        bound = grid.perimeter_bound(n)
        surface = {'internal_surface_border_radians': surface_internal / grid.length_scale,
                   'terrain_surface_border_radians': surface_imposed / grid.length_scale}
    thin = sum(len(graph[cell]) <= 2 and
               sum(terrain[nb] == terrain[cell] for nb in grid.neighbors[cell]) >= 4
               for cell in cells)
    return {'internal_border_hex_edges': internal,
            **surface,
            'terrain_border_hex_edges': imposed,
            'terrain_adjusted_perimeter_efficiency': min(1.0, bound / weighted) if weighted else 1.0,
            'internal_diameter_lower_bound': diameter,
            'normalized_internal_diameter': diameter / math.sqrt(n),
            'avoidable_thin_hex_fraction': thin / n,
            'single_hex_neck_fraction': neck / max(1, n - 1)}


def shape_error(province, efficiency):
    adjusted = province.get('terrain_adjusted_perimeter_efficiency', efficiency)
    elongation = min(1, max(0, province.get('normalized_internal_diameter', 0) - 3) / 3)
    thin = min(1, province.get('avoidable_thin_hex_fraction', 0) / .05)
    # Raw neck severity is reported separately: a natural isthmus is not a
    # subdivision defect. Avoidable thin cells contribute to the shape penalty.
    return .7 * (1 - adjusted) + .2 * elongation + .1 * thin
