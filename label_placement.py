"""Interior label anchors measured in the displayed SVG coordinate system."""
import heapq
import math


def signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def inside(x, y, ring):
    result = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            result = not result
    return result


def simplify(ring):
    # Remove subdivision points on straight SVG borders before distance queries.
    result = []
    for i, b in enumerate(ring):
        a, c = ring[i - 1], ring[(i + 1) % len(ring)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-12:
            result.append(b)
    return result or ring


def interior_anchor(rings, precision=.15):
    """Find an approximate maximum-clearance interior point, including holes.

    A cell's distance plus its half-diagonal bounds the best possible clearance
    within it. Subdivide only cells that can improve the current best point.
    """
    segments = [(a, b) for ring in rings for a, b in zip(ring, ring[1:] + ring[:1])]
    def distance(x, y):
        minimum = math.inf
        for a, b in segments:
            dx, dy = b[0] - a[0], b[1] - a[1]
            length2 = dx * dx + dy * dy
            t = max(0., min(1., ((x - a[0]) * dx + (y - a[1]) * dy) / length2)) if length2 else 0.
            minimum = min(minimum, (x - a[0] - t * dx) ** 2 + (y - a[1] - t * dy) ** 2)
        in_region = sum(inside(x, y, ring) for ring in rings) % 2
        return math.sqrt(minimum) * (1 if in_region else -1)

    outer = rings[0]
    minx, maxx = min(p[0] for p in outer), max(p[0] for p in outer)
    miny, maxy = min(p[1] for p in outer), max(p[1] for p in outer)
    width, height = maxx - minx, maxy - miny
    precision = min(precision, min(width, height) / 100)
    x, y = (minx + maxx) / 2, (miny + maxy) / 2
    best = (distance(x, y), x, y)
    queue = []
    def push(x, y, h):
        d = distance(x, y)
        heapq.heappush(queue, (-(d + h * math.sqrt(2)), x, y, h, d))
    push(x, y, max(width, height) / 2)
    while queue:
        bound, x, y, h, d = heapq.heappop(queue)
        if d > best[0]:
            best = (d, x, y)
        if -bound - best[0] <= precision:
            continue
        h /= 2
        for dx, dy in ((-h, -h), (h, -h), (-h, h), (h, h)):
            push(x + dx, y + dy, h)
    clearance, x, y = best
    return x, y, clearance


def projected_labels(rings, text):
    """One label per visible outer ring, sized to its available interior space."""
    rings = [simplify(ring) for ring in rings]
    holes = [ring for ring in rings if signed_area(ring) < 0]
    for outer in rings:
        area = signed_area(outer)
        if area <= 0:
            continue
        local_holes = [hole for hole in holes if inside(*hole[0], outer)]
        x, y, clearance = interior_anchor([outer, *local_holes])
        area -= sum(abs(signed_area(hole)) for hole in local_holes)
        nominal = min(10., max(2.5, math.sqrt(max(0., area)) * .1))
        # Conservative text bounding circle, including the white text stroke.
        font = min(nominal, .9 * clearance / (math.hypot(.4 * len(text), .75) + .1))
        yield x, y, font
