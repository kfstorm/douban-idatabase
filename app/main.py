import signal
from fastapi import FastAPI, HTTPException, Query, Depends, Response, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from sqlalchemy.orm import Session
from typing import List, Optional
from prometheus_client import CONTENT_TYPE_LATEST
import time
import multiprocessing
import uvicorn

from app import models, schemas
from app.database import get_db, init_db
from app.info_provider.tmdb import get_imdb_id_from_tmdb_id, get_imdb_id_from_tvdb_id
from app.logging_config import setup_logging
from app.schedule.scheduler import start_scheduler, stop_scheduler
from app.config import settings
from app.metrics import (
    get_metrics,
    api_requests_total,
    api_request_duration,
    user_requests_total,
)
from app.rate_limit import rate_limit_middleware
from app.redis_utils import (
    is_redis_available,
    get_from_cache,
    set_in_cache,
)
import app.utils

# Initialize logging
logger = setup_logging()

# Cache expiration times (in seconds)
TMDB_CACHE_EXPIRY = 60 * 60 * 24 * 30  # 30 days
TVDB_CACHE_EXPIRY = 60 * 60 * 24 * 30  # 30 days


def make_tmdb_cache_key(tmdb_id: str, media_type: str) -> str:
    """Make a cache key for TMDB to IMDb mapping"""
    return f"tmdb_to_imdb:{media_type}:{tmdb_id}"


def make_tvdb_cache_key(tvdb_id: str) -> str:
    """Make a cache key for TVDB to IMDb mapping"""
    return f"tvdb_to_imdb:{tvdb_id}"


# API Key security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def get_client_ip(request: Request) -> str:
    """
    Extract the client's real IP address from request headers.
    When behind Nginx, we check X-Forwarded-For and X-Real-IP headers.
    """
    # X-Forwarded-For header contains client IPs in order: client, proxy1, proxy2, ...
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in the list which is the client's real IP
        return forwarded_for.split(",")[0].strip()

    # X-Real-IP header contains the original client IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to the direct client IP if no proxy headers are present
    return request.client.host


# API Key verification dependency
def verify_api_key(
    request: Request,
    api_key_header: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Security(api_key_query),
    db: Session = Depends(get_db),
):
    # Get API key from header or query
    api_key = api_key_header or api_key_query

    if not api_key:
        # If anonymous access is allowed, use IP-based rate limiting
        if settings.ALLOW_ANONYMOUS_API_ACCESS:
            # Get real client IP address
            client_ip = get_client_ip(request)
            anonymous_info = {
                "user_id": client_ip,
                "rate_limit": settings.ANONYMOUS_RATE_LIMIT,
                "window_size": settings.ANONYMOUS_WINDOW_SIZE,
                "admin": False,
            }
            request.state.user_info = anonymous_info
            return anonymous_info
        # If no API key is provided and anonymous access is not allowed,
        # return 401 Unauthorized
        raise HTTPException(status_code=401, detail="API Key required")
    else:
        # Check if API key exists in user table
        user = models.get_user_by_api_key(db, api_key)
        if user and not user.disabled:
            user_info = {
                "user_id": user.user_id,
                "rate_limit": user.rate_limit,
                "window_size": user.window_size,
                "admin": user.admin,
            }
            request.state.user_info = user_info
            return user_info
        raise HTTPException(status_code=403, detail="Invalid API Key")


# API rate limiting - applied globally after authentication
def apply_rate_limiting(request: Request):
    # Only apply rate limiting for /api paths
    if request.url.path.startswith("/api"):
        # Get user info from state (set by verify_api_key)
        user_info = getattr(request.state, "user_info", None)

        if user_info:
            # Track user-specific request metrics
            user_requests_total.labels(
                user_id=str(user_info["user_id"]), endpoint=request.url.path
            ).inc()

            # Apply rate limiting
            rate_limit_middleware(request, user_info)


# Initialize FastAPI with global dependencies
my_app = FastAPI(
    dependencies=[
        Depends(verify_api_key),  # First verify API key
        Depends(apply_rate_limiting),  # Then apply rate limiting
    ]
)

# Add CORS middleware to allow cross-origin requests
my_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@my_app.middleware("http")
async def global_middleware(request: Request, call_next):
    # Record start time for metrics
    start_time = time.time()

    # Process the request - rate limiting is handled by global dependencies
    response = await call_next(request)

    # Add rate limit headers to response if they exist
    rate_limit_headers = getattr(request.state, "rate_limit_headers", None)
    if rate_limit_headers:
        for header_name, header_value in rate_limit_headers.items():
            response.headers[header_name] = header_value

    # Record metrics
    endpoint = request.url.path
    method = request.method
    status = response.status_code

    # Record request count
    api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()

    # Record request duration
    api_request_duration.labels(endpoint=endpoint, method=method).observe(
        time.time() - start_time
    )

    return response


@my_app.get("/api/item", response_model=List[schemas.Item])
def get_items(
    response: Response,
    douban_id: str = Query(None),
    imdb_id: str = Query(None),
    douban_title: str = Query(None),
    tmdb_id: str = Query(None),
    tmdb_media_type: str = Query(None),
    tvdb_id: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get items by various IDs:
    - douban_id: Douban ID
    - imdb_id: IMDB ID
    - douban_title: Exact Douban title match
    - tmdb_id: TMDB ID (will be converted to IMDB ID)
    - tmdb_media_type: "movie" or "tv" (only used with tmdb_id)
    - tvdb_id: TVDB ID (will be converted to IMDB ID)

    At least one ID parameter must be provided.
    """
    items = []

    # Check if we have any valid parameters
    has_direct_identifiers = any([douban_id, imdb_id, douban_title])
    has_external_identifiers = any([tmdb_id, tvdb_id])

    if not has_direct_identifiers and not has_external_identifiers:
        raise HTTPException(
            status_code=400,
            detail="At least one ID parameter must be provided",
        )

    # If we have direct identifiers, use them first
    if has_direct_identifiers:
        items = models.get_items(db, douban_id, imdb_id, douban_title)
    else:
        # If we don't have direct identifiers or no items were found with them,
        # try to use external identifiers (TMDB, TVDB)

        external_imdb_id = None

        # Validate media_type parameter when using TMDB ID
        if tmdb_id:
            if not tmdb_media_type:
                raise HTTPException(
                    status_code=400,
                    detail="tmdb_media_type is required when using tmdb_id",
                )
            if tmdb_media_type not in ["movie", "tv"]:
                raise HTTPException(
                    status_code=400,
                    detail="tmdb_media_type must be either 'movie' or 'tv'",
                )
            # Get IMDB ID from TMDB ID using cached function
            external_imdb_id = cached_get_imdb_id_from_tmdb_id(tmdb_id, tmdb_media_type)
        elif tvdb_id:
            # Get IMDB ID from TVDB ID using cached function
            external_imdb_id = cached_get_imdb_id_from_tvdb_id(tvdb_id)

        if external_imdb_id:
            # Try to find items with the IMDB ID we got from external sources
            items = models.get_items(db, imdb_id=external_imdb_id)

    if items:
        # Set cache for 7 days (604800 seconds) for successful responses
        response.headers["Cache-Control"] = "max-age=604800"
        return items

    # If we get here, no items were found
    # Set cache for 1 day (86400 seconds) for 404 responses
    raise HTTPException(
        status_code=404,
        detail="No items found",
        headers={"Cache-Control": "max-age=86400"},
    )


def cached_get_imdb_id_from_tmdb_id(tmdb_id: str, media_type: str) -> Optional[str]:
    """
    Get IMDB ID from TMDB ID with Redis caching

    Args:
        tmdb_id: TMDB ID
        media_type: 'movie' or 'tv'

    Returns:
        IMDB ID or None if not found
    """
    if not tmdb_id or not media_type:
        return None

    # Try to get from cache first
    if is_redis_available():
        cache_key = make_tmdb_cache_key(tmdb_id, media_type)
        cached_value = get_from_cache(cache_key)
        if cached_value is not None:
            # Return None for empty string (we cache empty strings for not found IDs)
            if cached_value == b"":
                return None
            # Return the cached IMDB ID
            return cached_value.decode("utf-8")

    # Not in cache, call the API
    imdb_id = get_imdb_id_from_tmdb_id(tmdb_id, media_type)

    # Save result in cache
    if is_redis_available():
        cache_key = make_tmdb_cache_key(tmdb_id, media_type)
        # Cache empty string for None values
        value_to_cache = imdb_id if imdb_id else ""
        set_in_cache(cache_key, value_to_cache, TMDB_CACHE_EXPIRY)

    return imdb_id


def cached_get_imdb_id_from_tvdb_id(tvdb_id: str) -> Optional[str]:
    """
    Get IMDB ID from TVDB ID with Redis caching

    Args:
        tvdb_id: TVDB ID

    Returns:
        IMDB ID or None if not found
    """
    if not tvdb_id:
        return None

    # Try to get from cache first
    if is_redis_available():
        cache_key = make_tvdb_cache_key(tvdb_id)
        cached_value = get_from_cache(cache_key)
        if cached_value is not None:
            # Return None for empty string (we cache empty strings for not found IDs)
            if cached_value == b"":
                return None
            # Return the cached IMDB ID
            return cached_value.decode("utf-8")

    # Not in cache, call the API
    imdb_id = get_imdb_id_from_tvdb_id(tvdb_id)

    # Save result in cache
    if is_redis_available():
        cache_key = make_tvdb_cache_key(tvdb_id)
        # Cache empty string for None values
        value_to_cache = imdb_id if imdb_id else ""
        set_in_cache(cache_key, value_to_cache, TVDB_CACHE_EXPIRY)

    return imdb_id


@my_app.get("/metrics")
def metrics_endpoint(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_api_key)
):
    """Expose Prometheus metrics, only accessible to admin users"""
    # Check if user has admin privileges
    if not current_user.get("admin", False):
        raise HTTPException(
            status_code=403, detail="Admin privileges required to access metrics"
        )

    return Response(content=get_metrics(db), media_type=CONTENT_TYPE_LATEST)


def run_app():
    """Run the FastAPI app"""
    uvicorn.run("app.main:my_app", host="0.0.0.0")


def main():
    """Main entry point that runs both the app and scheduler"""
    # Initialize database before starting workers
    logger.info("Initializing database in main process...")
    init_db()
    logger.info("Database initialized successfully")

    # Make sure the metrics module is imported first in the main process
    # This ensures the PROMETHEUS_MULTIPROC_DIR is set correctly
    logger.info("Initializing metrics...")
    from app.metrics import prometheus_multiproc_dir

    logger.info(f"Using Prometheus multiprocess directory: {prometheus_multiproc_dir}")

    # Start app in separate process
    logger.info("Starting FastAPI application...")
    app_process = multiprocessing.Process(target=run_app)
    app_process.start()

    if not settings.DISABLE_SCHEDULER:
        # Start scheduler in main process - only one instance will run
        logger.info("Starting scheduler in main process...")
        start_scheduler()
    else:
        logger.warning("Scheduler is disabled")

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        _exit_gracefully(app_process)

    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Wait for the app process to complete
        app_process.join()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down gracefully...")
        _exit_gracefully(app_process)


def _exit_gracefully(app_process):
    """Handle graceful exit"""
    app.utils.shutdown_flag = True
    if not settings.DISABLE_SCHEDULER:
        stop_scheduler()
    app_process.terminate()
    app_process.join()


if __name__ == "__main__":
    main()
