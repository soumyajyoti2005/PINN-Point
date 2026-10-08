from fastapi.testclient import TestClient
from fastapi import status
from app.main import app

client = TestClient(app)

from unittest.mock import patch

@patch("app.api.routes_health.check_postgres", return_value=True)
@patch("app.api.routes_health.check_influx", return_value=True)
@patch("app.api.routes_health.check_redis", return_value=True)
@patch("app.api.routes_health.check_mqtt", return_value=True)
def test_health_ok(mock_mqtt, mock_redis, mock_influx, mock_pg):
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"
    
def test_readings_stub():
    assert client.get("/api/v1/nodes/123/readings").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.post("/api/v1/readings").status_code == status.HTTP_501_NOT_IMPLEMENTED

def test_rainfall_stub():
    assert client.post("/api/v1/rainfall").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.get("/api/v1/rainfall").status_code == status.HTTP_501_NOT_IMPLEMENTED

def test_detection_stub():
    assert client.post("/api/v1/detect").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.get("/api/v1/detections").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.get("/api/v1/detections/1").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.patch("/api/v1/detections/1").status_code == status.HTTP_501_NOT_IMPLEMENTED

def test_simulation_stub():
    assert client.post("/api/v1/simulation/run").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.post("/api/v1/simulation/replay").status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert client.post("/api/v1/simulation/replay/stop").status_code == status.HTTP_501_NOT_IMPLEMENTED
