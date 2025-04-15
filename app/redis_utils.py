import logging
import redis
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Redis client instance
redis_client = None
USING_REDIS = False


def initialize_redis():
    """Initialize the Redis client if Redis URL is configured"""
    global redis_client, USING_REDIS

    # Check if Redis is configured
    if settings.REDIS_URL:
        # If Redis URL is configured, try to connect to Redis
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            USING_REDIS = True
            logger.info("Successfully connected to Redis")
        except Exception as e:
            # If Redis is configured but connection fails, log error but don't raise
            logger.error(f"Failed to connect to Redis: {e}")
            USING_REDIS = False
    else:
        # If Redis URL is not configured, don't use Redis
        USING_REDIS = False
        logger.info("Redis URL not configured, Redis features will be disabled")


def get_redis_client() -> Optional[redis.Redis]:
    """Get the Redis client instance"""
    global redis_client
    if redis_client is None:
        initialize_redis()
    return redis_client


def is_redis_available() -> bool:
    """Check if Redis is available"""
    return USING_REDIS and redis_client is not None


def get_from_cache(key: str) -> Optional[bytes]:
    """
    Get a value from the Redis cache

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    if not is_redis_available():
        return None

    try:
        return redis_client.get(key)
    except Exception as e:
        logger.error(f"Error getting value from Redis cache: {e}")
        return None


def set_in_cache(key: str, value: str, expiry: int = 0) -> bool:
    """
    Set a value in the Redis cache

    Args:
        key: Cache key
        value: Value to cache
        expiry: Expiration time in seconds (0 for no expiration)

    Returns:
        True if successful, False otherwise
    """
    if not is_redis_available():
        return False

    try:
        redis_client.set(key, value, ex=expiry if expiry > 0 else None)
        return True
    except Exception as e:
        logger.error(f"Error setting value in Redis cache: {e}")
        return False


# Initialize Redis on module import
initialize_redis()
