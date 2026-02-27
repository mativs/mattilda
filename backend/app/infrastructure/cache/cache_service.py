import json
import uuid

from redis.exceptions import RedisError

from app.infrastructure.cache.redis_client import get_redis_client


def get_json(cache_key: str) -> dict | None:
    try:
        raw = get_redis_client().get(cache_key)
    except RedisError:
        return None
    if raw is None or not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def set_json(cache_key: str, value: dict, ttl_seconds: int) -> None:
    try:
        get_redis_client().setex(cache_key, ttl_seconds, json.dumps(value, default=str))
    except (RedisError, TypeError, ValueError):
        return


def delete_key(cache_key: str) -> None:
    try:
        get_redis_client().delete(cache_key)
    except RedisError:
        return


def acquire_lock(lock_key: str, ttl_seconds: int) -> str | None:
    token = str(uuid.uuid4())
    try:
        acquired = bool(get_redis_client().set(lock_key, token, nx=True, ex=ttl_seconds))
    except RedisError:
        return token
    return token if acquired else None


def release_lock(lock_key: str, token: str) -> None:
    release_script = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""
    try:
        get_redis_client().eval(release_script, 1, lock_key, token)
    except RedisError:
        return
