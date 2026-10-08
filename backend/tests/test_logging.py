from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_logging_request_id_returned_when_valid():
    response = client.get("/api/v1/network", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"

def test_logging_request_id_generated_when_missing():
    response = client.get("/api/v1/network")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] != ""

def test_logging_request_id_replaced_when_invalid():
    response = client.get("/api/v1/network", headers={"X-Request-ID": "invalid value with spaces"})
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] != "invalid value with spaces"
