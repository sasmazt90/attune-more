"""Trace existing measured line support for display; never fabricate box edges."""
import numpy as np
from skimage.morphology import skeletonize


def measured_line_paths(values, valid, x, y, scale, origin=(0, 0)):
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('INVALID_DISPLAY_SCALE')
    support = skeletonize((np.asarray(values) > 0) & np.asarray(valid, dtype=bool))
    points = {tuple(p) for p in np.argwhere(support)}
    if len(points) > 20000:
        return []
    neighbors = {p: sorted((p[0]+dy, p[1]+dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy or dx) and (p[0]+dy, p[1]+dx) in points) for p in points}
    visited, paths = set(), []
    starts = sorted(points, key=lambda p: (len(neighbors[p]) == 2, p))
    for start in starts:
        for following in neighbors[start]:
            edge = tuple(sorted((start, following)))
            if edge in visited:
                continue
            path, previous, current = [start], start, following
            visited.add(edge)
            while True:
                path.append(current)
                choices = [p for p in neighbors[current] if p != previous and tuple(sorted((current, p))) not in visited]
                if len(neighbors[current]) != 2 or not choices:
                    break
                following = choices[0]
                visited.add(tuple(sorted((current, following))))
                previous, current = current, following
            if len(path) >= 3:
                paths.append([dict(x=(x+px+.5)/scale+origin[0], y=(y+py+.5)/scale+origin[1]) for py, px in path])
            if len(paths) >= 1024:
                return paths
    return paths
