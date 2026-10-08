import pytest
from app.sim.area import Area, haversine_m

def test_area_bbox_symmetry():
    # 22.6196 N, 88.3477 E with 300m half size
    area = Area(name="test", center_lat=22.6196, center_lon=88.3477, half_size_m=300.0)
    south, west, north, east = area.bbox()
    
    # Check north-south span
    ns_span = haversine_m(south, area.center_lon, north, area.center_lon)
    # Check east-west span (at center latitude, roughly but wait, haversine_m along east/west edges)
    # Actually, we can check east-west span along the center latitude or the top/bottom edges.
    ew_span = haversine_m(area.center_lat, west, area.center_lat, east)
    
    # Check spans are ~600m within 1% (6m)
    assert abs(ns_span - 600.0) < 6.0
    assert abs(ew_span - 600.0) < 6.0
    
    # Check symmetry
    assert area.center_lat == (south + north) / 2
    assert area.center_lon == (west + east) / 2

def test_area_from_env(monkeypatch):
    monkeypatch.setenv("AREA_NAME", "test-area")
    monkeypatch.setenv("AREA_CENTER_LAT", "20.0")
    monkeypatch.setenv("AREA_CENTER_LON", "30.0")
    monkeypatch.setenv("AREA_HALF_SIZE_M", "100.5")
    
    area = Area.from_env()
    assert area.name == "test-area"
    assert area.center_lat == 20.0
    assert area.center_lon == 30.0
    assert area.half_size_m == 100.5

def test_area_from_env_missing(monkeypatch):
    monkeypatch.delenv("AREA_NAME", raising=False)
    with pytest.raises(ValueError, match="Missing AREA_NAME"):
        Area.from_env()
