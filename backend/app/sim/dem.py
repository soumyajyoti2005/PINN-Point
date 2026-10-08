import os
import argparse
from app.sim.area import Area
from glob import glob

def find_dem(data_dir: str):
    dem_dir = os.path.join(data_dir, "dem")
    tifs = glob(os.path.join(dem_dir, "*.tif"))
    if not tifs:
        return None
    return tifs[0]

def sample_dem(path: str, points_lonlat: list[tuple[float, float]]):
    import rasterio
    import numpy as np
    
    with rasterio.open(path) as src:
        # rasterio.sample expects an iterable of (lon, lat) tuples
        gen = src.sample(points_lonlat)
        elevations = []
        for val in gen:
            # val is an array of band values, we assume band 1 is elevation
            v = val[0]
            if v == src.nodata:
                elevations.append(np.nan)
            else:
                elevations.append(float(v))
        return elevations

def robust_ground(path: str, points_lonlat: list[tuple[float, float]], radius_px: int = 1, percentile: float = 10):
    import rasterio
    import numpy as np
    
    results = []
    with rasterio.open(path) as src:
        band1 = src.read(1)
        for lon, lat in points_lonlat:
            try:
                row, col = src.index(lon, lat)
            except Exception:
                results.append(np.nan)
                continue
            
            # Get window bounds
            r_min = max(0, row - radius_px)
            r_max = min(src.height, row + radius_px + 1)
            c_min = max(0, col - radius_px)
            c_max = min(src.width, col + radius_px + 1)
            
            window_data = band1[r_min:r_max, c_min:c_max]
            valid_pixels = window_data[window_data != src.nodata]
            
            if valid_pixels.size == 0:
                results.append(np.nan)
            else:
                results.append(float(np.percentile(valid_pixels, percentile)))
    return results

def describe_dem(area: Area, path: str):
    import rasterio
    
    south, west, north, east = area.bbox()
    
    with rasterio.open(path) as src:
        # Approximate intersection by sampling a small grid of the bbox
        import numpy as np
        
        lons = np.linspace(west, east, num=50)
        lats = np.linspace(south, north, num=50)
        
        points = []
        for lat in lats:
            for lon in lons:
                points.append((lon, lat))
                
        elevations = sample_dem(path, points)
        elevations = [e for e in elevations if not np.isnan(e)]
        
        if not elevations:
            return {
                "min": np.nan, "max": np.nan, "relief": np.nan,
                "p5": np.nan, "p10": np.nan, "p50": np.nan, "p90": np.nan, "p95": np.nan,
                "pixel_size_x": src.res[0], "pixel_size_y": src.res[1]
            }
            
        min_elev = min(elevations)
        max_elev = max(elevations)
        return {
            "min": min_elev,
            "max": max_elev,
            "relief": max_elev - min_elev,
            "p5": np.percentile(elevations, 5),
            "p10": np.percentile(elevations, 10),
            "p50": np.percentile(elevations, 50),
            "p90": np.percentile(elevations, 90),
            "p95": np.percentile(elevations, 95),
            "pixel_size_x": src.res[0],
            "pixel_size_y": src.res[1]
        }

if __name__ == "__main__":
    import sys
    data_dir = os.environ.get("DATA_DIR", "/data")
    dem_path = find_dem(data_dir)
    
    if not dem_path:
        print("no DEM found in /data/dem; builder will use a synthetic gentle slope (elevation_source=synthetic)")
        sys.exit(0)
        
    area = Area.from_env()
    
    try:
        import rasterio.errors
        desc = describe_dem(area, dem_path)
    except rasterio.errors.RasterioIOError:
        print(f"DEM file at {dem_path} is unreadable or incomplete; re-download it")
        sys.exit(1)
    
    print(f"DEM found: {dem_path}")
    print(f"Pixel Size: {desc['pixel_size_x']:.5f} x {desc['pixel_size_y']:.5f} degrees")
    print(f"Bbox Elevation Range: {desc['min']:.2f} m to {desc['max']:.2f} m")
    print(f"Relief in Area: {desc['relief']:.2f} m")
    print(f"Percentiles: 5th={desc['p5']:.2f}, 10th={desc['p10']:.2f}, 50th={desc['p50']:.2f}, 90th={desc['p90']:.2f}, 95th={desc['p95']:.2f}")
