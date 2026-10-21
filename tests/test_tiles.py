"""Tests for Terrarium tile caching and decoding."""

from __future__ import annotations

import numpy as np
import pytest
import requests
from PIL import Image

from elevation_route import tiles


@pytest.fixture(autouse=True)
def tmp_cache(isolated_cache):
    return isolated_cache


def write_png(path, rgb_pixels):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(rgb_pixels, dtype=np.uint8), mode="RGB").save(path)
    return path


def test_tile_cache_path_layout(tmp_cache):
    p = tiles.tile_cache_path(10, 3, 4)
    assert p == tmp_cache / "10" / "3" / "4.png"


def test_load_tile_terrarium_decoding(tmp_cache):
    # elevation = R * 256 + G + B / 256 - 32768
    pixels = np.zeros((256, 256, 3), dtype=np.uint8)
    pixels[0, 0] = (128, 0, 0)        # 0.0 m
    pixels[0, 1] = (128, 1, 128)      # 1.5 m
    pixels[1, 0] = (130, 255, 255)    # 767.996... m
    pixels[1, 1] = (127, 0, 0)        # -256.0 m
    write_png(tiles.tile_cache_path(5, 6, 7), pixels)

    elev = tiles.load_tile(5, 6, 7)
    assert elev.shape == (256, 256)
    assert elev[0, 0] == pytest.approx(0.0)
    assert elev[0, 1] == pytest.approx(1.5)
    assert elev[1, 0] == pytest.approx(768.0, abs=0.01)
    assert elev[1, 1] == pytest.approx(-256.0)


def test_load_tile_missing_returns_none(tmp_cache):
    assert tiles.load_tile(1, 2, 3) is None


def test_load_tile_corrupt_file_returns_none(tmp_cache):
    path = tiles.tile_cache_path(1, 2, 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a png")
    assert tiles.load_tile(1, 2, 3) is None


def test_download_tile_refetches_corrupt_cache_entry(tmp_cache, monkeypatch):
    # A >100-byte non-PNG body (e.g. an S3 error page) must not be trusted.
    path = tiles.tile_cache_path(4, 5, 6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"<Error>AccessDenied</Error>" + b"x" * 120)

    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse(tiles.PNG_MAGIC + b"v" * 200)

    monkeypatch.setattr(tiles, "SESSION", FakeSession())
    assert tiles.download_tile(4, 5, 6) is True
    assert tiles._looks_like_png(path.read_bytes()[:8])


def test_download_tile_uses_cache_without_network(tmp_cache, monkeypatch):
    path = tiles.tile_cache_path(4, 5, 6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tiles.PNG_MAGIC + b"x" * 200)

    class Boom:
        def get(self, *args, **kwargs):
            raise AssertionError("cache hit must not touch the network")

    monkeypatch.setattr(tiles, "SESSION", Boom())
    assert tiles.download_tile(4, 5, 6) is True


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code


def test_download_tile_writes_cache(tmp_cache, monkeypatch):
    calls = []

    class FakeSession:
        def get(self, url, timeout=None):
            calls.append(url)
            return FakeResponse(tiles.PNG_MAGIC + b"e" * 200)

    monkeypatch.setattr(tiles, "SESSION", FakeSession())
    assert tiles.download_tile(8, 9, 10) is True

    path = tiles.tile_cache_path(8, 9, 10)
    assert path.exists()
    assert path.stat().st_size > 100
    assert len(calls) == 1
    assert "/8/9/10.png" in calls[0]


def test_download_tile_falls_back_to_second_mirror(tmp_cache, monkeypatch):
    calls = []

    class FakeSession:
        def get(self, url, timeout=None):
            calls.append(url)
            if len(calls) == 1:
                raise requests.RequestException("boom")
            return FakeResponse(tiles.PNG_MAGIC + b"e" * 200)

    monkeypatch.setattr(tiles, "SESSION", FakeSession())
    assert tiles.download_tile(8, 9, 10) is True
    assert len(calls) == 2
    assert tiles.tile_cache_path(8, 9, 10).exists()


def test_download_tile_failure_warns(tmp_cache, monkeypatch, capsys):
    class FakeSession:
        def get(self, url, timeout=None):
            raise requests.RequestException("down")

    monkeypatch.setattr(tiles, "SESSION", FakeSession())
    assert tiles.download_tile(8, 9, 10) is False

    err = capsys.readouterr().err
    assert "Warning: could not download tile 8/9/10" in err
    assert not tiles.tile_cache_path(8, 9, 10).exists()


def test_download_tile_rejects_non_png_body(tmp_cache, monkeypatch, capsys):
    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse(b"<Error>AccessDenied</Error>" + b"x" * 120)

    monkeypatch.setattr(tiles, "SESSION", FakeSession())
    assert tiles.download_tile(8, 9, 10) is False
    assert not tiles.tile_cache_path(8, 9, 10).exists()
    assert "could not download tile" in capsys.readouterr().err


def test_download_tiles_downloads_all(tmp_cache, monkeypatch):
    got = []

    def fake_download(zoom, x, y):
        got.append((zoom, x, y))
        return True

    monkeypatch.setattr(tiles, "download_tile", fake_download)
    tiles.download_tiles(7, 10, 11, 20, 21)
    assert sorted(got) == [
        (7, 10, 20),
        (7, 10, 21),
        (7, 11, 20),
        (7, 11, 21),
    ]
