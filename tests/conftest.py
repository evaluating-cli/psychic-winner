"""Shared test setup: headless matplotlib, src/ import path, isolated cache."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from elevation_route import cli, tiles  # noqa: E402  (needs SRC on sys.path)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Keep tile-cache writes inside the test tmp dir, never the real HOME."""
    cache = tmp_path / "tile-cache"
    monkeypatch.setattr(tiles, "CACHE_DIR", cache)
    monkeypatch.setattr(cli, "CACHE_DIR", cache)
    return cache
