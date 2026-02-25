from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.cache.redis_client import redis_is_available


def get_dummy_status(db: Session, redis_client) -> dict:
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    return {
        "message": "Hello from Mattilda FastAPI backend",
        "db_connected": db_connected,
        "redis_connected": redis_is_available(redis_client),
    }
