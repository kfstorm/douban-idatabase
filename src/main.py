from fastapi import FastAPI, HTTPException, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db, init_db
from .logging_config import setup_logging
from .scheduler import start_scheduler, stop_scheduler

# Initialize logging
logger = setup_logging()

app = FastAPI()

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


@app.get("/api/item", response_model=List[schemas.Item])
def get_items(
    response: Response,
    douban_id: int = Query(None),
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
