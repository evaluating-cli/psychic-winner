"""
A* least-cost pathfinding over a DEM grid.

Cost of one step::

    cost = distance + elev_weight * abs(delta_elevation)
"""

from __future__ import annotations

import heapq
import math

import numpy as np

from .geo import haversine_km

NEIGHBORS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


def find_path(
    elev: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    px: np.ndarray,
    py: np.ndarray,
    elev_weight: float,
):
    """
    A* least-cost path.

    Costs:
        cost = distance + elev_weight * abs(delta_elevation)
    """
    rows, cols = elev.shape
    si, sj = start
    gi, gj = goal

    g = np.full((rows, cols), np.inf, dtype=np.float64)
    parent = np.full((rows, cols), -1, dtype=np.int64)

    start_lin = si * cols + sj
    g[si, sj] = 0.0
    parent[si, sj] = start_lin

    h0 = math.hypot(px[gj] - px[sj], py[gi] - py[si])
    heap = [(h0, 0.0, si, sj)]

    while heap:
        _, current_cost, i, j = heapq.heappop(heap)

        if current_cost > g[i, j] + 1e-12:
            continue

        if (i, j) == (gi, gj):
            break

        for di, dj in NEIGHBORS:
            vi = i + di
            vj = j + dj

            if vi < 0 or vi >= rows or vj < 0 or vj >= cols:
                continue

            dh = elev[vi, vj] - elev[i, j]
            if math.isnan(dh):
                continue

            dh = abs(dh)

            step_dist = math.hypot(px[vj] - px[j], py[vi] - py[i])
            new_cost = current_cost + step_dist + elev_weight * dh

            if new_cost < g[vi, vj] - 1e-12:
                g[vi, vj] = new_cost
                parent[vi, vj] = i * cols + j

                h = math.hypot(px[gj] - px[vj], py[gi] - py[vi])
                heapq.heappush(heap, (new_cost + h, new_cost, vi, vj))

    if not np.isfinite(g[gi, gj]):
        return None

    # Reconstruct path.
    path = []
    current = gi * cols + gj

    while current != start_lin:
        i, j = divmod(current, cols)
        path.append((i, j))
        current = int(parent[i, j])

    path.append((si, sj))
    path.reverse()

    return path


def path_statistics(
    path: list[tuple[int, int]],
    elev: np.ndarray,
    lons: np.ndarray,
    lats: np.ndarray,
):
    path_i = [p[0] for p in path]
    path_j = [p[1] for p in path]

    path_elev = elev[path_i, path_j]
    path_lons = lons[path_j]
    path_lats = lats[path_i]

    distance_km = 0.0
    for k in range(len(path) - 1):
        distance_km += haversine_km(
            path_lats[k],
            path_lons[k],
            path_lats[k + 1],
            path_lons[k + 1],
        )

    diffs = np.diff(path_elev)
    ascent = float(np.sum(diffs[diffs > 0]))
    descent = float(-np.sum(diffs[diffs < 0]))
    elevation_range = float(np.max(path_elev) - np.min(path_elev))

    return path_lons, path_lats, path_elev, distance_km, ascent, descent, elevation_range
