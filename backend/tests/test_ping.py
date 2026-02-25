def test_ping_endpoint_returns_dummy_payload(client):
    """
    Validate the public health endpoint payload.

    1. Call the public ping endpoint without authentication.
    2. Parse the response payload returned by the backend.
    3. Validate the expected message value.
    4. Validate DB and Redis connectivity flags are true.
    """
    response = client.get("/api/v1/ping")
    assert response.status_code == 200

    payload = response.json()
    assert payload["message"] == "Hello from Mattilda FastAPI backend"
    assert payload["db_connected"] is True
    assert payload["redis_connected"] is True
