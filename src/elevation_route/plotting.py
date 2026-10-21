"""
Topographic map rendering: hillshade, elevation tint, contours and route.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource


def plot_route(
    elev: np.ndarray,
    lons: np.ndarray,
    lats: np.ndarray,
    px: np.ndarray,
    py: np.ndarray,
    path_lons: np.ndarray,
    path_lats: np.ndarray,
    bbox: tuple[float, float, float, float],
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
    title: str,
    outfile: str,
    show: bool,
) -> None:
    west, south, east, north = bbox

    fig, ax = plt.subplots(figsize=(12, 8))

    # Hillshade.
    cell_x = abs(px[1] - px[0]) if len(px) > 1 else 1.0
    cell_y = abs(py[1] - py[0]) if len(py) > 1 else 1.0

    ls = LightSource(azdeg=315, altdeg=45)
    shaded = ls.hillshade(elev, vert_exag=1.0, dx=cell_x, dy=cell_y)

    ax.imshow(
        shaded,
        cmap="gray",
        extent=(west, east, south, north),
        origin="lower",
        alpha=0.5,
        zorder=1,
    )

    im = ax.imshow(
        elev,
        cmap="terrain",
        extent=(west, east, south, north),
        origin="lower",
        alpha=0.55,
        zorder=2,
    )

    # Contour/topographic lines.
    elev_min = float(np.nanmin(elev))
    elev_max = float(np.nanmax(elev))

    step = 50
    if elev_max - elev_min < 300:
        step = 25
    elif elev_max - elev_min > 2000:
        step = 200

    levels = np.arange(
        np.floor(elev_min / step) * step,
        elev_max + step,
        step,
    )

    ax.contour(
        lons,
        lats,
        elev,
        levels=levels,
        colors="black",
        linewidths=0.4,
        alpha=0.5,
        zorder=3,
    )

    # Route.
    ax.plot(
        path_lons,
        path_lats,
        color="red",
        linewidth=2.5,
        zorder=5,
        label="Low-elevation-change path",
    )

    ax.scatter(*start_coords, color="green", marker="^", s=120, zorder=6, label="Start")
    ax.scatter(*end_coords, color="blue", marker="*", s=140, zorder=6, label="Destination")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(alpha=0.3)

    fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02, label="Elevation (m)")

    out_path = Path(outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)

    print(f"Plot written to {out_path}")
