"""
Download, cache and decode Terrarium elevation tiles.

Terrarium elevation encoding::

    elevation = (R * 256 + G + B / 256) - 32768
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from .net import SESSION

TILE_URLS = [
    "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png",
]

CACHE_DIR = Path.home() / ".elevation_route_cache"


def tile_cache_path(zoom: int, x: int, y: int) -> Path:
    return CACHE_DIR / str(zoom) / str(x) / f"{y}.png"


def download_tile(zoom: int, x: int, y: int) -> bool:
    """Download one elevation tile into the local cache."""
    path = tile_cache_path(zoom, x, y)

    if path.exists() and path.stat().st_size > 100:
        return True

    for url_template in TILE_URLS:
        url = url_template.format(z=zoom, x=x, y=y)
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 100:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                return True
        except requests.RequestException:
            continue

    print(f"Warning: could not download tile {zoom}/{x}/{y}", file=sys.stderr)
    return False


def download_tiles(zoom: int, xmin: int, xmax: int, ymin: int, ymax: int) -> None:
    tasks = [
        (zoom, x, y)
        for x in range(xmin, xmax + 1)
        for y in range(ymin, ymax + 1)
    ]

    print(f"Downloading {len(tasks)} DEM tile(s) at zoom {zoom} ...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda t: download_tile(*t), tasks))


def load_tile(zoom: int, x: int, y: int) -> np.ndarray | None:
    """Load a cached terrarium elevation tile as a 256x256 elevation array."""
    path = tile_cache_path(zoom, x, y)
    if not path.exists():
        return None

    try:
        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    except Exception:
        return None

    # Terrarium elevation encoding:
    # elevation = (R * 256 + G + B / 256) - 32768
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0
