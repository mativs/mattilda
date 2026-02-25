from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ping_endpoint_returns_dummy_payload():
    response = client.get("/api/v1/ping")
    assert response.status_code == 200

    payload = response.json()
    assert payload["message"] == "Hello from Mattilda FastAPI backend"
    assert "db_connected" in payload
    assert "redis_connected" in payload
