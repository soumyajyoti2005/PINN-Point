import pytest

def test_osmnx_import():
    ox = pytest.importorskip("osmnx", reason="osmnx not installed in api image")
    import app.sim.osm_fetch
    assert hasattr(app.sim.osm_fetch, "fetch_roads")

def test_rasterio_import():
    rio = pytest.importorskip("rasterio", reason="rasterio not installed in api image")
    import app.sim.dem
    assert hasattr(app.sim.dem, "find_dem")
