from __future__ import annotations
import numpy as np
from skimage.morphology import skeletonize

NEIGHBORS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def _rdp(points: list[tuple[int, int]], eps: float = 1.25) -> list[tuple[int, int]]:
    if len(points) < 3:
        return points
    x1, y1 = points[0]
    x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = float(np.hypot(dx, dy))
    best_i, best_d = 0, -1.0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = (
            float(np.hypot(px - x1, py - y1))
            if norm < 1e-6
            else abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        )
        if d > best_d:
            best_i, best_d = i, d
    if best_d <= eps:
        return [points[0], points[-1]]
    left = _rdp(points[: best_i + 1], eps)
    right = _rdp(points[best_i:], eps)
    return left[:-1] + right


def _trace_skeleton_paths(
    skel: np.ndarray, weight: np.ndarray
) -> list[tuple[float, list[tuple[int, int]]]]:
    ys, xs = np.nonzero(skel)
    pixels = {(int(x), int(y)) for y, x in zip(ys, xs)}
    if not pixels:
        return []
    adj = {
        (x, y): [
            (x + dx, y + dy)
            for dx, dy in NEIGHBORS
            if (x + dx, y + dy) in pixels
        ]
        for x, y in pixels
    }
    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    raw_paths: list[list[tuple[int, int]]] = []

    def edge_key(a: tuple[int, int], b: tuple[int, int]):
        return (a, b) if a <= b else (b, a)

    def walk(start: tuple[int, int], nxt: tuple[int, int]) -> list[tuple[int, int]]:
        chain = [start, nxt]
        visited_edges.add(edge_key(start, nxt))
        prev, cur = start, nxt
        while len(adj[cur]) == 2:
            cand = [n for n in adj[cur] if n != prev]
            if not cand:
                break
            step = cand[0]
            ek = edge_key(cur, step)
            if ek in visited_edges:
                break
            visited_edges.add(ek)
            chain.append(step)
            prev, cur = cur, step
        return chain

    terminals = sorted([p for p, ns in adj.items() if len(ns) != 2])
    for start in terminals:
        for nxt in adj[start]:
            if edge_key(start, nxt) not in visited_edges:
                raw_paths.append(walk(start, nxt))
    for start in sorted(pixels):
        for nxt in adj[start]:
            if edge_key(start, nxt) not in visited_edges:
                raw_paths.append(walk(start, nxt))

    scored: list[tuple[float, list[tuple[int, int]]]] = []
    for chain in raw_paths:
        if len(chain) < 5:
            continue
        length = sum(
            float(np.hypot(b[0] - a[0], b[1] - a[1]))
            for a, b in zip(chain, chain[1:])
        )
        if length < 5.0:
            continue
        mean_w = float(np.mean([weight[y, x] for x, y in chain]))
        simp = _rdp(chain, 1.15)
        if len(simp) >= 2:
            scored.append((length * (0.5 + mean_w), simp))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def measured_line_paths(
    ridge: np.ndarray,
    roi: np.ndarray,
    ref_scale: float,
    max_paths: int = 12,
) -> list[dict]:
    valid = roi & np.isfinite(ridge)
    if int(valid.sum()) < 40:
        return []
    vals = ridge[valid]
    q82 = float(np.percentile(vals, 82))
    thr = max(q82, max(ref_scale * 0.85, 1e-4))
    mask = valid & (ridge >= thr)
    if int(mask.sum()) < 6:
        return []
    skel = skeletonize(mask)
    scale = max(float(np.percentile(vals, 98)), thr, 1e-4)
    weight = np.clip(ridge / scale, 0.0, 1.0)
    traced = _trace_skeleton_paths(skel, weight)[:max_paths]
    out: list[dict] = []
    for idx, (score, pts) in enumerate(traced):
        strength = round(
            float(np.clip(np.mean([weight[y, x] for x, y in pts]), 0.15, 1.0)), 3
        )
        out.append(
            {
                "id": f"line-{idx + 1}",
                "strength": strength,
                "source": "skeletonized-highpass-ridge-v1",
                "points": [{"x": int(x), "y": int(y)} for x, y in pts],
            }
        )
    return out
