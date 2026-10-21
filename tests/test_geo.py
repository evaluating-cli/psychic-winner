"""Tests for geodesic helpers, tile math and geocoding."""

from __future__ import annotations

import math

import pytest

from elevation_route import geo


def test_haversine_zero_distance():
    assert geo.haversine_km(48.8566, 2.3522, 48.8566, 2.3522) == pytest.approx(0.0)


def test_haversine_one_degree_at_equator():
    # Quarter of the Earth circumference / 90 with R = 6371.0088 km.
    assert geo.haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.195, abs=1e-3)


def test_haversine_paris_berlin():
    dist = geo.haversine_km(48.8566, 2.3522, 52.5200, 13.4050)
    assert dist == pytest.approx(877.5, abs=1.0)


def test_haversine_symmetry():
    a = geo.haversine_km(10.0, 20.0, 30.0, 40.0)
    b = geo.haversine_km(30.0, 40.0, 10.0, 20.0)
    assert a == pytest.approx(b)


def test_haversine_antipodal_no_domain_error():
    # Near-antipodal points can push the haversine 'a' term 1 ulp above 1.0,
    # which used to crash math.asin with ValueError (regression test).
    lat1, lon1 = -58.83543353249384, 20.930552591388874
    lat2, lon2 = 58.835433532781714, 200.9305525921169
    d = geo.haversine_km(lat1, lon1, lat2, lon2)
    # Half the great-circle circumference with R = 6371.0088 km.
    assert d == pytest.approx(20015.1, abs=5.0)


def test_lonlat_to_tile_zoom_0():
    assert geo.lonlat_to_tile(0.0, 0.0, 0) == (0, 0)
    assert geo.lonlat_to_tile(179.9, 85.0, 0) == (0, 0)


def test_lonlat_to_tile_zoom_1():
    assert geo.lonlat_to_tile(0.0, 0.0, 1) == (1, 1)
    assert geo.lonlat_to_tile(-179.9, -85.0, 1) == (0, 1)


def test_lonlat_to_tile_zoom_10_origin():
    assert geo.lonlat_to_tile(0.0, 0.0, 10) == (512, 512)


def test_lonlat_to_tile_clamps_poles():
    # Latitude beyond the Web-Mercator limit must be clamped, not crash.
    x, y = geo.lonlat_to_tile(0.0, 89.9, 12)
    assert y == 0
    x, y = geo.lonlat_to_tile(0.0, -89.9, 12)
    assert y == (1 << 12) - 1


def test_tile_range_covers_bbox():
    bbox = (2.0, 48.0, 14.0, 53.0)  # roughly Paris -> Berlin
    zoom = 8
    xmin, xmax, ymin, ymax = geo.tile_range(bbox, zoom)

    west, south, east, north = bbox
    for lon, lat in [(west, north), (east, north), (west, south), (east, south)]:
        tx, ty = geo.lonlat_to_tile(lon, lat, zoom)
        assert xmin <= tx <= xmax
        assert ymin <= ty <= ymax


def test_choose_zoom_respects_tile_budget():
    # A huge bbox (Moscow -> Lisbon) must still yield <= 300 tiles when possible.
    bbox = (-10.0, 35.0, 40.0, 60.0)
    zoom, xmin, xmax, ymin, ymax = geo.choose_zoom(bbox)
    count = (xmax - xmin + 1) * (ymax - ymin + 1)
    assert 6 <= zoom <= 11
    if zoom > 6:
        assert count <= 300


def test_choose_zoom_prefers_detail_for_small_areas():
    bbox = (2.3, 48.8, 2.4, 48.9)  # inside Paris
    zoom, *_ = geo.choose_zoom(bbox)
    assert zoom == 11


def test_geocode_accepts_coordinates():
    lat, lon, label = geo.geocode("48.8566,2.3522")
    assert lat == pytest.approx(48.8566)
    assert lon == pytest.approx(2.3522)
    assert label == "48.8566,2.3522"


def test_geocode_invalid_latitude_falls_back_to_name_lookup(monkeypatch):
    class Boom:
        def get(self, *args, **kwargs):
            raise AssertionError("network should not be used for parsing")

    # 95 is an invalid latitude, so the input is treated as a name instead.
    monkeypatch.setattr(geo, "SESSION", Boom())
    with pytest.raises(AssertionError):
        geo.geocode("95.0,10.0")


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_geocode_name_lookup(monkeypatch):
    payload = [
        {
            "lat": "48.8566",
            "lon": "2.3522",
            "display_name": "Paris, Île-de-France, France",
        }
    ]

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            assert "nominatim" in url
            assert params["q"] == "Paris, France"
            return FakeResponse(payload)

    monkeypatch.setattr(geo, "SESSION", FakeSession())
    lat, lon, name = geo.geocode("Paris, France")
    assert lat == pytest.approx(48.8566)
    assert lon == pytest.approx(2.3522)
    assert name == "Paris, Île-de-France, France"


def test_geocode_no_results_raises(monkeypatch):
    class FakeSession:
        def get(self, url, params=None, timeout=None):
            return FakeResponse([])

    monkeypatch.setattr(geo, "SESSION", FakeSession())
    with pytest.raises(RuntimeError, match="Could not geocode"):
        geo.geocode("Nowhereville")
