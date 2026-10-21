"""
Terrain route minimiser for two European cities.

The route cost minimised is::

    cost = step_distance + elev_weight * |change_in_elevation|

A high ``elev_weight`` makes the route prefer flatter terrain.
"""

from __future__ import annotations

__version__ = "1.0.0"
