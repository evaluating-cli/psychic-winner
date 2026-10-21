"""Tests for A* least-cost pathfinding and route statistics."""

from __future__ import annotations

import numpy as np
import pytest

from elevation_route import dem, pathfinding
from elevation_route.geo import haversine_km


def metric_axes(rows, cols, step=100.0):
    px = np.arange(cols, dtype=np.float64) * step
    py = np.arange(rows, dtype=np.float64) * step
    return px, py


def test_flat_grid_shortest_path():
    rows = cols = 20
    elev = np.zeros((rows, cols))
    px, py = metric_axes(rows, cols)

    path = pathfinding.find_path(elev, (0, 0), (rows - 1, cols - 1), px, py, elev_weight=100.0)

    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (rows - 1, cols - 1)
    # Path is strictly monotone towards the goal (no detours on a flat grid).
    for (i1, j1), (i2, j2) in zip(path, path[1:]):
        assert max(abs(i2 - i1), abs(j2 - j1)) == 1
        assert i2 >= i1 and j2 >= j1


def test_flat_grid_distance_matches_metric_diagonal():
    rows = cols = 11
    elev = np.zeros((rows, cols))
    bbox = (2.0, 48.0, 2.01, 48.01)
    lons = np.linspace(bbox[0], bbox[2], cols)
    lats = np.linspace(bbox[1], bbox[3], rows)
    px, py = dem.make_projection(lons, lats, bbox)

    path = pathfinding.find_path(elev, (0, 0), (10, 10), px, py, elev_weight=100.0)
    *_, distance_km, ascent, descent, elev_range = pathfinding.path_statistics(
        path, elev, lons, lats
    )

    # Ten equal diagonal steps cover the same ground as the corner-to-corner
    # great-circle distance at this scale.
    expected_km = haversine_km(48.0, 2.0, 48.01, 2.01)
    assert distance_km == pytest.approx(expected_km, rel=1e-3)
    assert ascent == 0.0
    assert descent == 0.0
    assert elev_range == 0.0


def test_path_avoids_costly_ridge():
    rows = cols = 21
    elev = np.zeros((rows, cols))
    elev[:, 10] = 1000.0  # vertical ridge across the whole map
    elev[10, 10] = 0.0  # single mountain pass
    px, py = metric_axes(rows, cols)

    path = pathfinding.find_path(elev, (0, 0), (0, 20), px, py, elev_weight=100.0)
    assert path is not None

    # Must cross the ridge only through the pass.
    ridge_crossings = [(i, j) for (i, j) in path if j == 10]
    assert ridge_crossings == [(10, 10)]


def test_low_weight_takes_the_short_way_over_the_ridge():
    rows = cols = 21
    elev = np.zeros((rows, cols))
    elev[:, 10] = 1000.0
    elev[10, 10] = 0.0
    px, py = metric_axes(rows, cols)

    # With no elevation penalty the straight line over the ridge wins.
    path = pathfinding.find_path(elev, (0, 0), (0, 20), px, py, elev_weight=0.0)
    assert path is not None
    assert (0, 10) in path


def test_unreachable_goal_returns_none():
    rows = cols = 15
    elev = np.zeros((rows, cols))
    elev[7, 7] = np.nan  # goal cell itself is void
    px, py = metric_axes(rows, cols)

    path = pathfinding.find_path(elev, (0, 0), (7, 7), px, py, elev_weight=10.0)
    assert path is None


def test_nan_neighbours_are_not_crossed():
    rows = cols = 5
    elev = np.zeros((rows, cols))
    elev[2, :4] = np.nan  # barrier across columns 0-3, hole at column 4
    px, py = metric_axes(rows, cols)

    path = pathfinding.find_path(elev, (0, 0), (4, 4), px, py, elev_weight=10.0)
    assert path is not None
    assert not any(elev[i, j] != elev[i, j] for i, j in path)  # no NaN cells


def test_path_statistics_ascent_descent():
    elev = np.array(
        [
            [0.0, 10.0, 30.0, 10.0, 25.0],
        ]
    )
    lons = np.linspace(0.0, 0.01, 5)
    lats = np.array([45.0])
    path = [(0, j) for j in range(5)]

    path_lons, path_lats, path_elev, distance_km, ascent, descent, elev_range = (
        pathfinding.path_statistics(path, elev, lons, lats)
    )

    assert ascent == pytest.approx(10.0 + 20.0 + 15.0)
    assert descent == pytest.approx(20.0)
    assert elev_range == pytest.approx(30.0)
    assert distance_km > 0
    assert list(path_elev) == [0.0, 10.0, 30.0, 10.0, 25.0]
