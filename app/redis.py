import redis
import json
import logging
from typing import Optional
from .config import settings

logger = logging.getLogger("uvicorn.error")

try:
    redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=0,
        decode_responses=True,
        socket_connect_timeout=2
    )
    # Test connection
    redis_client.ping()
    logger.info("Connected to Redis successfully")
    redis_enabled = True
except Exception as e:
    logger.warning(f"Connecting to Redis failed. Caching will be disabled. Error: {e}")
    redis_client = None
    redis_enabled = False

def get_cache(key: str) -> Optional[dict]:
    if not redis_enabled or not redis_client:
        return None
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Error reading from Redis cache: {e}")
    return None

def set_cache(key: str, value: dict, expire_seconds: int = 86400):
    if not redis_enabled or not redis_client:
        return
    try:
        redis_client.setex(key, expire_seconds, json.dumps(value))
    except Exception as e:
        logger.warning(f"Error writing to Redis cache: {e}")
