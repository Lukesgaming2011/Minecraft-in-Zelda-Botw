"""Small deterministic helpers used by the live bridge."""
import math


def normalize(v):
    length = math.sqrt(sum(x*x for x in v))
    if not math.isfinite(length) or length < 1e-6:
        raise ValueError('Invalid view direction')
    return tuple(x/length for x in v)


def ray_box(origin, direction, center, half_extent, reach=8):
    near, far = 0.0, reach
    for o, d, c in zip(origin, direction, center):
        lo, hi = c-half_extent, c+half_extent
        if abs(d) < 1e-8:
            if not lo <= o <= hi:
                return None
            continue
        a, b = sorted(((lo-o)/d, (hi-o)/d))
        near, far = max(near, a), min(far, b)
        if near > far:
            return None
    return near


def snap(point, grid):
    return tuple(math.floor(x/grid + 0.5)*grid for x in point)
