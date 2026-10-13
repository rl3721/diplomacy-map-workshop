"""Pack named slots inside projected ocean outlines at one common radius."""
import math
from .label_placement import inside, simplify


def slot_positions(rings, count):
    rings = [simplify(r) for r in rings]
    points = [p for ring in rings for p in ring]
    x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
    y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
    segments = [(a, b) for r in rings for a, b in zip(r, r[1:] + r[:1])]
    candidates = []
    # Oversample the footprint; refine if narrow projected fragments need it.
    resolution = max(25, math.ceil(math.sqrt(count * 60)))
    while len(candidates) < count:
        for ix in range(resolution):
            x = x0 + (ix + .5) * (x1 - x0) / resolution
            for iy in range(resolution):
                y = y0 + (iy + .5) * (y1 - y0) / resolution
                if sum(inside(x, y, r) for r in rings) % 2 == 0:
                    continue
                clearance = math.inf
                for (ax, ay), (bx, by) in segments:
                    dx, dy = bx - ax, by - ay
                    norm = dx * dx + dy * dy
                    t = max(0, min(1, ((x-ax)*dx + (y-ay)*dy) / norm)) if norm else 0
                    clearance = min(clearance, math.hypot(x-ax-t*dx, y-ay-t*dy))
                candidates.append([clearance, x, y])
        resolution *= 2
    chosen = []
    for _ in range(count):
        best = max(range(len(candidates)), key=lambda i: candidates[i][0])
        clearance, x, y = candidates.pop(best)
        chosen.append((x, y, clearance))
        for candidate in candidates:
            candidate[0] = min(candidate[0], math.hypot(x-candidate[1], y-candidate[2]) / 2.2)
    return chosen
