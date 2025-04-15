import time
import logging
from fastapi import Request, HTTPException

from app.metrics import user_rate_limit_hits, user_rate_limit_current
from app.redis_utils import (
    is_redis_available,
    get_redis_client,
)

logger = logging.getLogger(__name__)

# In-memory rate limit store as a fallback when Redis is not available
rate_limit_store = {}


def rate_limit_middleware(request: Request, user_info: dict):
    """
    Implement API rate limiting middleware
    Using sliding window algorithm to limit user request frequency

    Args:
        request: FastAPI Request object
        user_info: User information dictionary

    Raises:
        HTTPException: If user exceeds the rate limit
    """
    user_id = user_info["user_id"]
    rate_limit = user_info["rate_limit"]
    window_size = user_info["window_size"]
    # Skip rate limiting if rate limit is 0
    if not rate_limit or not window_size:
        return
    now = int(time.time())

    # Create window key name
    window_key = f"rate_limit:{user_id}:{now // window_size}"

    if is_redis_available():
        # Use Redis for rate limiting
        redis_client = get_redis_client()
        current_count = redis_client.incr(window_key)
        if current_count == 1:
            # Set expiration time for new window
            redis_client.expire(window_key, window_size)

        remaining = max(0, rate_limit - current_count)
    else:
        # Use in-memory storage for rate limiting
        if window_key not in rate_limit_store:
            rate_limit_store[window_key] = 0

            # Clean up expired windows
            for key in list(rate_limit_store.keys()):
                key_time = int(key.split(":")[-1]) * window_size
                if now - key_time >= window_size:
                    del rate_limit_store[key]

        rate_limit_store[window_key] += 1
        current_count = rate_limit_store[window_key]
        remaining = max(0, rate_limit - current_count)

    # Track current rate limit usage in metrics
    user_rate_limit_current.labels(user_id=str(user_id)).set(current_count)

    # Add standard rate limit response headers
    # These headers follow industry best practices
    # for communicating rate limits to clients
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(rate_limit),  # Maximum requests allowed in the window
        "X-RateLimit-Remaining": str(remaining),  # Requests remaining in current window
        "X-RateLimit-Reset": str(
            (now // window_size + 1) * window_size
        ),  # Unix timestamp when window resets
    }

    # If limit is exceeded, raise an exception with standard headers
    if current_count > rate_limit:
        # Track rate limit hits in metrics
        user_rate_limit_hits.labels(user_id=str(user_id)).inc()

        reset_time = (now // window_size + 1) * window_size
        retry_after = reset_time - now

        # Status code 429 "Too Many Requests" is defined in RFC 6585
        # "Retry-After" is a standard header indicating when to retry
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Rate limit exceeded.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(rate_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
            },
        )
