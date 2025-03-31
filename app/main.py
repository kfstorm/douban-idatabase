from fastapi import FastAPI, HTTPException, Query, Depends, Response, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from sqlalchemy.orm import Session
from typing import List, Optional
from prometheus_client import CONTENT_TYPE_LATEST
from app import models, schemas
from app.database import get_db, init_db
from app.logging_config import setup_logging
from app.scheduler import start_scheduler, stop_scheduler
from app.config import settings
from app.metrics import (
    get_metrics,
    update_db_metrics,
    api_requests_total,
    api_request_duration,
)
import time

# Initialize logging
logger = setup_logging()

# API Key security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


# API Key verification dependency
async def verify_api_key(
    api_key_header: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Security(api_key_query),
):
    if settings.API_KEY == "":
        # If no API key is configured, refuse all requests
        raise HTTPException(status_code=500, detail="API Key not configured on server")

    if api_key_header == settings.API_KEY or api_key_query == settings.API_KEY:
        return True

    raise HTTPException(status_code=403, detail="Invalid or missing API Key")


# Initialize FastAPI with global dependency
app = FastAPI(dependencies=[Depends(verify_api_key)])

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.on_event("startup")
def on_startup():
    logger.info("Starting up the application...")
    init_db()
    logger.info("Database initialized successfully")
    # Start the scheduler
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    logger.info("Shutting down the application...")
    # Stop the scheduler
    stop_scheduler()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)

    # Skip metrics for the metrics endpoint itself
    if request.url.path != "/metrics":
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


@app.get("/api/item", response_model=List[schemas.Item])
def get_items(
    response: Response,
    douban_id: str = Query(None),
    imdb_id: str = Query(None),
    douban_title: str = Query(None),
    db: Session = Depends(get_db),
):
    if not any([douban_id, imdb_id, douban_title]):
        raise HTTPException(
            status_code=400,
            detail="At least one of douban_id, imdb_id, or douban_title must be provided",  # noqa: B950
        )

    items = models.get_items(db, douban_id, imdb_id, douban_title)
    if not items:
        # Set no-cache for 404 responses
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        raise HTTPException(status_code=404, detail="No items found")

    # Set cache for 1 day (86400 seconds) for successful responses
    response.headers["Cache-Control"] = "max-age=86400"
    return items


@app.get("/metrics")
def metrics_endpoint(db: Session = Depends(get_db)):
    """Expose Prometheus metrics"""
    # Update database metrics before returning
    update_db_metrics(db)

    return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)
