"""
Build a regular DEM grid from cached Terrarium tiles.
"""

from __future__ import annotations

import math
import sys

import numpy as np

from .tiles import load_tile


def build_dem(
    bbox: tuple[float, float, float, float],
    zoom: int,
    xmin: int,
    xmax: int,
    ymin: int,
    ymax: int,
    grid_size: int,
    loader=None,
):
    """
    Sample terrain tiles onto a regular lon/lat grid.

    ``loader`` is a callable ``(zoom, x, y) -> np.ndarray | None`` and defaults
    to :func:`elevation_route.tiles.load_tile`. It exists as an override hook
    for testing.
    """
    if loader is None:
        loader = load_tile

    west, south, east, north = bbox

    lons = np.linspace(west, east, grid_size)
    lats = np.linspace(south, north, grid_size)

    lon2, lat2 = np.meshgrid(lons, lats)

    n = 1 << zoom

    wx = (lon2 + 180.0) / 360.0
    lat_clipped = np.clip(lat2, -85.0511, 85.0511)
    wy = (1.0 - np.arcsinh(np.tan(np.radians(lat_clipped))) / np.pi) / 2.0

    tile_x = np.floor(wx * n).astype(int)
    tile_y = np.floor(wy * n).astype(int)

    px = (wx * n - tile_x) * 256.0
    py = (wy * n - tile_y) * 256.0

    elev = np.full(lon2.shape, np.nan, dtype=np.float32)
    missing_tiles: list[tuple[int, int]] = []

    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            tile = loader(zoom, x, y)
            if tile is None:
                missing_tiles.append((x, y))
                continue

            mask = (tile_x == x) & (tile_y == y)
            if not mask.any():
                continue

            ci = np.clip(np.floor(px[mask]).astype(int), 0, 255)
            ri = np.clip(np.floor(py[mask]).astype(int), 0, 255)

            elev[mask] = tile[ri, ci]

    if np.isnan(elev).any():
        missing = int(np.isnan(elev).sum())
        if missing_tiles:
            shown = ", ".join(f"{zoom}/{x}/{y}" for x, y in missing_tiles[:5])
            more = "" if len(missing_tiles) <= 5 else f" (+{len(missing_tiles) - 5} more)"
            print(
                f"Warning: {missing} DEM sample(s) missing; filling with 0. "
                f"Failed tile(s): {shown}{more}",
                file=sys.stderr,
            )
        else:
            print(f"Warning: {missing} DEM sample(s) missing; filling with 0", file=sys.stderr)
        elev = np.nan_to_num(elev, nan=0.0)

    return elev, lons, lats


def make_projection(
    lons: np.ndarray,
    lats: np.ndarray,
    bbox: tuple[float, float, float, float],
):
    """Simple local metric projection for route cost calculations."""
    west, south, east, north = bbox

    lat_mid = math.radians((north + south) / 2.0)
    lon_scale = 111320.0 * math.cos(lat_mid)
    lat_scale = 110540.0

    lon0 = (west + east) / 2.0
    lat0 = (north + south) / 2.0

    px = (lons - lon0) * lon_scale
    py = (lats - lat0) * lat_scale

    return px, py


def coord_to_grid(
    lat: float,
    lon: float,
    bbox: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> tuple[int, int]:
    """Map a lon/lat point to the nearest (row, col) on the DEM grid."""
    west, south, east, north = bbox
    x = (lon - west) / (east - west) * (shape[1] - 1)
    y = (lat - south) / (north - south) * (shape[0] - 1)
    return int(np.clip(round(y), 0, shape[0] - 1)), int(
        np.clip(round(x), 0, shape[1] - 1)
    )
