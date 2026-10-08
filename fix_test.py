import os

with open('backend/tests/test_dataset.py', 'r') as f:
    content = f.read()

# I will just write a new file instead to be completely clean
new_tests = """import pytest
pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")
pytest.importorskip("pyswmm")
import numpy as np
import os
import json
import uuid
import pyarrow.parquet as pq

from app.sim.storms import generate_storm, blockage_injection, apply_sensor_effects
from app.sim.generate_dataset import split_dataset
from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import generate_dataset

def test_storms():
    rng1 = np.random.default_rng(42)
    s1, p1 = generate_storm(rng1, max_peak_cap=80.0)
    
    rng2 = np.random.default_rng(42)
    s2, p2 = generate_storm(rng2, max_peak_cap=80.0)
    
    np.testing.assert_array_equal(s1, s2)
    assert p1 == p2

def test_apply_sensor_effects():
    clean = np.ones((10, 5)) * 2.0
    rng = np.random.default_rng(42)
    mask = np.array([True, False, True, False, True])
    depths_m = np.array([1.5, 3.0, 1.5, 3.0, np.inf])
    
    obs = apply_sensor_effects(clean, 0.0, 0.0, mask, rng, depths_m)
    
    # Check mask alignment and NaN
    assert not np.isnan(obs[0, 0])
    assert np.isnan(obs[0, 1])
    assert not np.isnan(obs[0, 2])
    assert np.isnan(obs[0, 3])
    assert not np.isnan(obs[0, 4])
    
    # Check rim clipping
    assert obs[0, 0] == 1.5  # Clipped to depth
    assert obs[0, 4] == 2.0  # Not clipped (inf)

def test_balanced_assignment_and_determinism(tmp_path, monkeypatch):
    # Determinism & balanced test
    os.makedirs(tmp_path / "swmm", exist_ok=True)
    os.makedirs(tmp_path / "datasets", exist_ok=True)
    
    network = {
        "nodes": [
            {"id": "n1", "is_outfall": False, "invert_elevation_m": 0, "depth_m": 2.0},
            {"id": "n2", "is_outfall": True, "invert_elevation_m": -1}
        ],
        "pipes": [
            {"id": f"p{i}", "from_node": "n1", "to_node": "n2", "length_m": 10, "diameter_m": 0.5, "manning_n": 0.01}
            for i in range(49)
        ]
    }
    with open(tmp_path / "swmm" / "test_network.json", "w") as f:
        json.dump(network, f)
        
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AREA_NAME", "test")
    monkeypatch.setenv("DATASET_NAME", "smoke1")
    monkeypatch.setenv("DATASET_RUNS", "49")
    monkeypatch.setenv("DATASET_DETECTABLE_M", "0.05")
    
    # mock pyswmm to avoid real sim
    class MockSim:
        def __init__(self, *args, **kwargs):
            self.nodes = [type("MockNode", (), {"nodeid": "n1", "depth": 1.0})(), 
                          type("MockNode", (), {"nodeid": "n2", "depth": 0.5})()]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def step_advance(self, step): pass
        def __iter__(self):
            yield 1
    
    import app.sim.generate_dataset
    monkeypatch.setattr(app.sim.run_swmm.pyswmm, "Simulation", MockSim)
    
    # just mock run_swmm itself to be faster
    def mock_run(inp):
        return {
            "status": "success",
            "depths": np.array([[1.0, 0.5], [1.0, 0.5]]),
            "node_ids": ["n1", "n2"],
            "runoff_err_pct": 0.0, "routing_err_pct": 0.0, "flood_volume_m3": 0.0
        }
    monkeypatch.setattr(app.sim.generate_dataset, "run_simulation", mock_run)
    
    generate_dataset()
    
    man1 = pq.read_table(str(tmp_path / "datasets" / "smoke1" / "manifest.parquet")).to_pandas()
    
    # Balanced assignment check
    blocks = man1[man1["severity"] > 0]
    # Exactly 1 of each severity per storm
    for s_id, group in blocks.groupby("storm_id"):
        assert sorted(group["severity"].tolist()) == [0.3, 0.6, 0.9]
    # Pipe counts differ by max 1
    counts = blocks["blocked_pipe_id"].value_counts()
    assert counts.max() - counts.min() <= 1
    
    # Determinism check
    monkeypatch.setenv("DATASET_NAME", "smoke2")
    generate_dataset()
    man2 = pq.read_table(str(tmp_path / "datasets" / "smoke2" / "manifest.parquet")).to_pandas()
    pd.testing.assert_frame_equal(man1.drop(columns=["run_id"]), man2.drop(columns=["run_id"]))
    
    # Mask alignment check
    npz1 = np.load(str(tmp_path / "datasets" / "smoke1" / f"storm_0000_block_0.npz"))
    obs = npz1["observed"]
    mask = npz1["sensor_mask"]
    # non-NaN cols == mask
    assert np.array_equal(~np.isnan(obs[0]), mask)

def test_detectable_flag(tmp_path, monkeypatch):
    os.makedirs(tmp_path / "swmm", exist_ok=True)
    os.makedirs(tmp_path / "datasets", exist_ok=True)
    network = {
        "nodes": [{"id": "n1", "is_outfall": False, "invert_elevation_m": 0, "depth_m": 2.0},
                  {"id": "n2", "is_outfall": True, "invert_elevation_m": -1}],
        "pipes": [{"id": "p1", "from_node": "n1", "to_node": "n2", "length_m": 10, "diameter_m": 0.5, "manning_n": 0.01}]
    }
    with open(tmp_path / "swmm" / "test_network.json", "w") as f: json.dump(network, f)
        
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AREA_NAME", "test")
    monkeypatch.setenv("DATASET_NAME", "smoke_detect")
    monkeypatch.setenv("DATASET_RUNS", "1")
    monkeypatch.setenv("DATASET_DETECTABLE_M", "0.05")
    
    call_counts = {"base": 0, "block": 0}
    def mock_run(inp):
        # return different depths to trigger detectability
        if "0.0500" in inp: # 0.9 severity of 0.5 is 0.05
            d = np.array([[1.5, 0.5], [1.5, 0.5]])
            call_counts["block"] += 1
        else:
            d = np.array([[1.0, 0.5], [1.0, 0.5]])
            call_counts["base"] += 1
        return {
            "status": "success", "depths": d, "node_ids": ["n1", "n2"],
            "runoff_err_pct": 0.0, "routing_err_pct": 0.0, "flood_volume_m3": 0.0
        }
    import app.sim.generate_dataset
    monkeypatch.setattr(app.sim.generate_dataset, "run_simulation", mock_run)
    generate_dataset()
    man = pq.read_table(str(tmp_path / "datasets" / "smoke_detect" / "manifest.parquet")).to_pandas()
    blocks = man[man["severity"] == 0.9]
    if len(blocks) > 0:
        row = blocks.iloc[0]
        assert row["peak_signal_m"] == 0.5  # 1.5 - 1.0
        assert row["detectable"] == True
"""

with open('backend/tests/test_dataset.py', 'w') as f:
    f.write(new_tests)
