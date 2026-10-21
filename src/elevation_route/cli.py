"""
Command-line interface for the terrain route minimiser.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from . import __version__
from .dem import build_dem, coord_to_grid, make_projection
from .geo import choose_zoom, geocode, haversine_km, tile_range
from .pathfinding import find_path, path_statistics
from .plotting import plot_route
from .tiles import CACHE_DIR, download_tiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Route between two European cities favouring low elevation change."
    )
    parser.add_argument("city1", help="First city, e.g. 'Paris, France'")
    parser.add_argument("city2", help="Second city, e.g. 'Berlin, Germany'")
    parser.add_argument("--grid-size", type=int, default=700, help="DEM grid resolution")
    parser.add_argument(
        "--elev-weight",
        type=float,
        default=100.0,
        help="How much 1 metre of elevation change costs relative to 1 metre of distance. Default: 100",
    )
    parser.add_argument("--buffer-km", type=float, default=None, help="Extra bounding-box margin")
    parser.add_argument("--zoom", type=int, default=None, help="Force terrain-tile zoom")
    parser.add_argument("--output", default="route_topomap.png", help="Output PNG path")
    parser.add_argument("--show", action="store_true", help="Show plot interactively")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args(argv)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        lat1, lon1, name1 = geocode(args.city1)
        lat2, lon2, name2 = geocode(args.city2)
    except Exception as e:
        print(f"Geocoding error: {e}", file=sys.stderr)
        return 2

    print(f"{name1}: {lat1:.5f}, {lon1:.5f}")
    print(f"{name2}: {lat2:.5f}, {lon2:.5f}")

    straight_km = haversine_km(lat1, lon1, lat2, lon2)

    if args.buffer_km:
        buffer_deg = args.buffer_km / 111.0
    else:
        buffer_deg = max(0.3, straight_km * 0.15 / 111.0)

    bbox = (
        min(lon1, lon2) - buffer_deg,
        min(lat1, lat2) - buffer_deg,
        max(lon1, lon2) + buffer_deg,
        max(lat1, lat2) + buffer_deg,
    )

    if args.zoom:
        zoom = args.zoom
        xmin, xmax, ymin, ymax = tile_range(bbox, zoom)
    else:
        zoom, xmin, xmax, ymin, ymax = choose_zoom(bbox)

    download_tiles(zoom, xmin, xmax, ymin, ymax)

    elev, lons, lats = build_dem(bbox, zoom, xmin, xmax, ymin, ymax, args.grid_size)

    start = coord_to_grid(lat1, lon1, bbox, elev.shape)
    goal = coord_to_grid(lat2, lon2, bbox, elev.shape)

    px, py = make_projection(lons, lats, bbox)

    print("Running A* pathfinding ...")
    path = find_path(elev, start, goal, px, py, args.elev_weight)

    if path is None:
        print("No path found.", file=sys.stderr)
        return 1

    path_lons, path_lats, path_elev, route_km, ascent, descent, elevation_range = path_statistics(
        path, elev, lons, lats
    )

    print("\nResults")
    print("-------")
    print(f"Straight-line distance:      {straight_km:8.1f} km")
    print(f"Route distance:              {route_km:8.1f} km")
    print(f"Total ascent:                {ascent:8.0f} m")
    print(f"Total descent:               {descent:8.0f} m")
    print(f"Total |elevation change|:    {ascent + descent:8.0f} m")
    print(f"Elevation range on route:    {elevation_range:8.0f} m")

    title = (
        f"Low-elevation-change route: {name1} -> {name2}\n"
        f"{route_km:.1f} km, {ascent:.0f} m ascent"
    )

    plot_route(
        elev,
        lons,
        lats,
        px,
        py,
        path_lons,
        path_lats,
        bbox,
        (lon1, lat1),
        (lon2, lat2),
        title,
        args.output,
        args.show,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
