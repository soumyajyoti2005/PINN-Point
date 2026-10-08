import numpy as np

def test_resample_time_series():
    from app.sim.generate_dataset import resample_time_series
    raw_times = [0.0, 15.0, 45.0, 60.0, 65.0, 120.0]
    raw_depths = [[1.0], [2.0], [4.0], [5.0], [5.0], [6.0]]
    t_grid, d_interp = resample_time_series(raw_times, raw_depths, target_duration_s=120)
    
    assert len(t_grid) == 3
    assert t_grid[0] == 0.0
    assert t_grid[1] == 60.0
    assert t_grid[2] == 120.0
    
    assert d_interp[0, 0] == 1.0
    assert d_interp[1, 0] == 5.0
    assert d_interp[2, 0] == 6.0

def test_npz_t_min_arange_121(tmp_path, monkeypatch):
    import os, json, pyarrow.parquet as pq
    os.makedirs(tmp_path / "swmm", exist_ok=True)
    os.makedirs(tmp_path / "datasets", exist_ok=True)
    network = {
        "nodes": [{"id": "n1", "is_outfall": False, "lon": 88.370, "lat": 22.579, "invert_elevation_m": 0, "depth_m": 2.0},
                  {"id": "n2", "is_outfall": True, "lon": 88.371, "lat": 22.579, "invert_elevation_m": -1}],
        "pipes": [{"id": "p1", "from_node": "n1", "to_node": "n2", "length_m": 10, "diameter_m": 0.5, "manning_n": 0.01}]
    }
    with open(tmp_path / "swmm" / "test_network.json", "w") as f: json.dump(network, f)
        
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AREA_NAME", "test")
    monkeypatch.setenv("DATASET_NAME", "smoke_tmin")
    monkeypatch.setenv("DATASET_RUNS", "1")
    
    from app.sim.generate_dataset import generate_dataset
    generate_dataset()
    
    man = pq.read_table(str(tmp_path / "datasets" / "smoke_tmin" / "manifest.parquet")).to_pandas()
    for _, row in man.iterrows():
        npz = np.load(str(tmp_path / "datasets" / "smoke_tmin" / f"{row['run_id']}.npz"))
        assert np.array_equal(npz["t_min"], np.arange(121))
