from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch

client = TestClient(app)

@patch("app.api.routes_health.check_postgres", return_value=True)
@patch("app.api.routes_health.check_influx", return_value=True)
@patch("app.api.routes_health.check_redis", return_value=True)
@patch("app.api.routes_health.check_mqtt", return_value=True)
def test_health_check_ok(mock_mqtt, mock_redis, mock_influx, mock_pg):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["postgres"] == "ok"

@patch("app.api.routes_health.check_postgres", return_value=False)
@patch("app.api.routes_health.check_influx", return_value=True)
@patch("app.api.routes_health.check_redis", return_value=True)
@patch("app.api.routes_health.check_mqtt", return_value=True)
def test_health_check_degraded(mock_mqtt, mock_redis, mock_influx, mock_pg):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["postgres"] == "down"
    assert response.json()["influx"] == "ok"
