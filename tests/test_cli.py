"""Offline end-to-end tests for the CLI."""

from __future__ import annotations

import numpy as np
import pytest

from elevation_route import cli, dem


@pytest.fixture
def offline_world(monkeypatch, tmp_path):
    """Replace geocoding, downloads and terrain with deterministic stand-ins."""
    monkeypatch.setattr(
        cli,
        "geocode",
        lambda name: {
            "A": (48.85, 2.35, "City A"),
            "B": (49.25, 2.65, "City B"),
        }[name],
    )
    monkeypatch.setattr(cli, "download_tiles", lambda *args: None)

    def fake_loader(zoom, x, y):
        yy, xx = np.mgrid[0:256, 0:256]
        hill = 400.0 * np.exp(-((xx - 128) ** 2 + (yy - 128) ** 2) / (2 * 60.0**2))
        return hill.astype(np.float32)

    monkeypatch.setattr(dem, "load_tile", fake_loader)
    return tmp_path


def test_full_run_writes_map_and_stats(offline_world, capsys):
    out = offline_world / "map.png"

    rc = cli.main(["A", "B", "--grid-size", "24", "--output", str(out)])

    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 0

    printed = capsys.readouterr().out
    assert "Results" in printed
    assert "Straight-line distance" in printed
    assert "Total ascent" in printed
    assert "Plot written to" in printed


def test_geocode_failure_exits_2(monkeypatch, capsys):
    def boom(name):
        raise RuntimeError("no such place")

    monkeypatch.setattr(cli, "geocode", boom)

    rc = cli.main(["Nowhere", "Else"])
    assert rc == 2
    assert "Geocoding error" in capsys.readouterr().err


def test_no_path_exits_1(offline_world, monkeypatch, capsys):
    monkeypatch.setattr(cli, "find_path", lambda *args, **kwargs: None)

    rc = cli.main(["A", "B", "--grid-size", "12", "--output", str(offline_world / "x.png")])
    assert rc == 1
    assert "No path found." in capsys.readouterr().err


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_version_flag(capsys):
    from elevation_route import __version__

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
