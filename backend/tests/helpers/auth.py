from app.application.services.security_service import create_access_token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def school_header(token: str, school_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-School-Id": str(school_id)}


def token_for_user(user_id: int) -> str:
    return create_access_token(user_id)
