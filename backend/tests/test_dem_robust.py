import pytest

def test_dem_robust(tmp_path):
    np = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    from app.sim.dem import robust_ground, sample_dem
    from rasterio.transform import from_origin
    
    arr = np.full((5, 5), 5.0, dtype=rasterio.float32)
    arr[2, 2] = 30.0 # building spike
    
    transform = from_origin(88.0, 22.0, 0.01, 0.01)
    tif_path = str(tmp_path / "test.tif")
    
    with rasterio.open(
        tif_path,
        'w',
        driver='GTiff',
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=arr.dtype,
        crs='+proj=latlong',
        transform=transform,
        nodata=-9999.0
    ) as dst:
        dst.write(arr, 1)
        
    lon, lat = 88.025, 21.975
    
    samp = sample_dem(tif_path, [(lon, lat)])
    assert samp[0] == 30.0
    
    rob = robust_ground(tif_path, [(lon, lat)], radius_px=1, percentile=10)
    assert rob[0] == 5.0
