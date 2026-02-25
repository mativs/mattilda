from redis import Redis
from redis.exceptions import RedisError

from app.config import settings


def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def redis_is_available(client: Redis) -> bool:
    try:
        return bool(client.ping())
    except RedisError:
        return False
