from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.health_service import get_dummy_status
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/ping")
def ping(db: Session = Depends(get_db)):
    redis_client = get_redis_client()
    return get_dummy_status(db=db, redis_client=redis_client)
