from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict
import logging
from . import models, schemas, crawler
from .database import get_db, init_db
from .logging_config import setup_logging
from .scheduler import start_scheduler, stop_scheduler

# Initialize logging
logger = setup_logging()

app = FastAPI()


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
    douban_id: int = Query(None),
    imdb_id: str = Query(None),
    douban_title: str = Query(None),
    db: Session = Depends(get_db),
):
    if not any([douban_id, imdb_id, douban_title]):
        raise HTTPException(
            status_code=400,
            detail="At least one of douban_id, imdb_id, or douban_title must be provided",
        )

    items = models.get_items(db, douban_id, imdb_id, douban_title)
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    return items


@app.post("/api/crawler/search")
def trigger_google_search(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger a Google search for recent Douban movie pages.
    The search runs in the background to avoid timeouts.
    Returns nothing.
    """
    background_tasks.add_task(crawler.search_recent_douban_movies, db)
    return {}


@app.get("/api/crawler/search-sync")
def trigger_google_search_sync(db: Session = Depends(get_db)):
    """
    Trigger a Google search for recent Douban movie pages and wait for completion.
    May time out for large searches.
    Returns nothing.
    """
    crawler.search_recent_douban_movies(db)
    return {}
