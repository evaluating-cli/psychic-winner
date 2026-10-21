"""Tests for DEM assembly and the local metric projection."""

from __future__ import annotations

import numpy as np
import pytest

from elevation_route import dem, geo


def constant_loader(value):
    def loader(zoom, x, y):
        return np.full((256, 256), value, dtype=np.float32)

    return loader


def test_build_dem_shape_and_values():
    bbox = (2.0, 48.0, 3.0, 49.0)
    zoom = 8
    xmin, xmax, ymin, ymax = geo.tile_range(bbox, zoom)

    elev, lons, lats = dem.build_dem(
        bbox, zoom, xmin, xmax, ymin, ymax, grid_size=16,
        loader=constant_loader(42.0),
    )

    assert elev.shape == (16, 16)
    assert np.allclose(elev, 42.0)
    assert lons[0] == pytest.approx(2.0)
    assert lons[-1] == pytest.approx(3.0)
    assert lats[0] == pytest.approx(48.0)
    assert lats[-1] == pytest.approx(49.0)


def test_build_dem_missing_tiles_filled_with_zero(capsys):
    bbox = (2.0, 48.0, 3.0, 49.0)
    zoom = 8
    xmin, xmax, ymin, ymax = geo.tile_range(bbox, zoom)
    assert xmax > xmin, "test needs a multi-tile bbox"

    # Only the left tile column is available.
    def loader(z, x, y):
        return np.full((256, 256), 100.0, dtype=np.float32) if x == xmin else None

    elev, lons, lats = dem.build_dem(
        bbox, zoom, xmin, xmax, ymin, ymax, grid_size=20, loader=loader
    )

    assert elev.shape == (20, 20)
    assert 0.0 in elev  # filled
    assert 100.0 in elev  # real samples
    assert "missing" in capsys.readouterr().out


def test_build_dem_missing_without_loader_hook(monkeypatch):
    bbox = (2.0, 48.0, 3.0, 49.0)
    zoom = 8
    xmin, xmax, ymin, ymax = geo.tile_range(bbox, zoom)
    monkeypatch.setattr(dem, "load_tile", lambda z, x, y: None)

    elev, lons, lats = dem.build_dem(bbox, zoom, xmin, xmax, ymin, ymax, grid_size=10)
    assert np.allclose(elev, 0.0)


def test_make_projection_centre_is_origin():
    bbox = (2.0, 48.0, 3.0, 49.0)
    lons = np.array([2.0, 2.5, 3.0])
    lats = np.array([48.0, 48.5, 49.0])

    px, py = dem.make_projection(lons, lats, bbox)

    assert px[1] == pytest.approx(0.0)
    assert py[1] == pytest.approx(0.0)
    assert px[2] == pytest.approx(-px[0])
    assert py[2] == pytest.approx(-py[0])
    # 1 degree of latitude ~ 110540 m.
    assert py[2] == pytest.approx(0.5 * 110540.0)
    # 1 degree of longitude at 48.5 N scales by cos(lat).
    lat_mid = np.deg2rad(48.5)
    assert px[2] == pytest.approx(0.5 * 111320.0 * np.cos(lat_mid))


def test_coord_to_grid_corners():
    bbox = (2.0, 48.0, 3.0, 49.0)
    shape = (11, 21)

    assert dem.coord_to_grid(48.0, 2.0, bbox, shape) == (0, 0)
    assert dem.coord_to_grid(49.0, 3.0, bbox, shape) == (10, 20)


def test_coord_to_grid_center_and_clipping():
    bbox = (2.0, 48.0, 3.0, 49.0)
    shape = (11, 11)

    assert dem.coord_to_grid(48.5, 2.5, bbox, shape) == (5, 5)
    # Out-of-bbox coordinates clamp instead of indexing out of range.
    assert dem.coord_to_grid(50.0, 10.0, bbox, shape) == (10, 10)  # north-east
    assert dem.coord_to_grid(40.0, -5.0, bbox, shape) == (0, 0)  # south-west
