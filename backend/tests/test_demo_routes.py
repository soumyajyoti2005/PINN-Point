import os
import json
from fastapi.testclient import TestClient
from fastapi import status
from app.main import app

client = TestClient(app)

def test_demo_routes(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    
    # Setup network
    swmm_dir = data_dir / "swmm"
    swmm_dir.mkdir()
    net_path = swmm_dir / "kolkata-amherst_network.json"
    net_path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"id": 1}]}))
    
    # Setup scenarios
    replay_dir = data_dir / "replay"
    replay_dir.mkdir()
    index_path = replay_dir / "index.json"
    index_path.write_text(json.dumps([{"scenario_id": "scen_1"}]))
    
    scen_path = replay_dir / "scen_1.json"
    scen_path.write_text(json.dumps({"scenario_id": "scen_1", "v": 1}))
    
    # Test network
    res = client.get("/api/v1/network")
    assert res.status_code == 200
    assert len(res.json()["features"]) == 1
    
    # Test scenarios
    res = client.get("/api/v1/scenarios")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["scenario_id"] == "scen_1"
    
    # Test replay
    res = client.get("/api/v1/replay/scen_1")
    assert res.status_code == 200
    assert res.json()["v"] == 1
    
    # Test not found
    res = client.get("/api/v1/replay/not_exist")
    assert res.status_code == 404

