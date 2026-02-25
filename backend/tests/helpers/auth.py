def login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def school_header(token: str, school_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-School-Id": str(school_id)}
