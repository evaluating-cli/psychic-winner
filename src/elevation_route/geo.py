"""
Geodesic helpers and geocoding.
"""

from __future__ import annotations

import math

from .net import SESSION


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points."""
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(name: str) -> tuple[float, float, str]:
    """
    Geocode a place name with Nominatim.
    Also accepts "lat,lon".
    """
    s = name.strip()

    # Allow direct coordinates.
    parts = s.split(",")
    if len(parts) == 2:
        try:
            lat = float(parts[0])
            lon = float(parts[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon, s
        except ValueError:
            pass

    params = {
        "q": s,
        "format": "jsonv2",
        "limit": 1,
    }

    r = SESSION.get("https://nominatim.openstreetmap.org/search", params=params, timeout=30)
    r.raise_for_status()

    data = r.json()
    if not data:
        raise RuntimeError(f"Could not geocode: {name}")

    return (
        float(data[0]["lat"]),
        float(data[0]["lon"]),
        data[0].get("display_name", s),
    )


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    """Convert lon/lat to slippy-map tile x/y."""
    n = 1 << zoom
    lat = max(min(lat, 85.0511), -85.0511)

    x = (lon + 180.0) / 360.0
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0

    return int(x * n), int(y * n)


def tile_range(bbox: tuple[float, float, float, float], zoom: int):
    """Return tile range xmin, xmax, ymin, ymax covering bbox."""
    west, south, east, north = bbox

    xmin, ymin = lonlat_to_tile(west, north, zoom)
    xmax, _ = lonlat_to_tile(east, north, zoom)
    _, ymax = lonlat_to_tile(west, south, zoom)

    return xmin, xmax, ymin, ymax


def choose_zoom(bbox: tuple[float, float, float, float]):
    """Pick a zoom level that avoids downloading too many small tiles."""
    for zoom in range(11, 5, -1):
        xmin, xmax, ymin, ymax = tile_range(bbox, zoom)
        count = (xmax - xmin + 1) * (ymax - ymin + 1)
        if count <= 300:
            return zoom, xmin, xmax, ymin, ymax

    zoom = 6
    xmin, xmax, ymin, ymax = tile_range(bbox, zoom)
    return zoom, xmin, xmax, ymin, ymax
