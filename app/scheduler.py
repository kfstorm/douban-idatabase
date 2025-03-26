import logging
import threading
import time
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal
from .worker import process_queue_item
from .crawler import search_recent_douban_movies

logger = logging.getLogger(__name__)

# Flags to control the scheduler threads
running = False
scheduler_thread = None
google_scheduler_thread = None

# Configuration
GOOGLE_SEARCH_INTERVAL_SECONDS = 3600  # Run Google search every hour


def queue_processor():
    """Background thread that processes queue items periodically"""
    global running

    logger.info("Queue processor started")

    while running:
        try:
            db = SessionLocal()
            process_items_in_queue(db)
            db.close()
        except Exception as e:
            logger.exception(f"Error in queue processor: {e}")

        # Sleep for 10 seconds before checking queue again
        time.sleep(10)

    logger.info("Queue processor stopped")


def process_items_in_queue(db: Session):
    """Process a batch of items from the queue"""
    try:
        # Process up to 5 items per batch
        for _ in range(5):
            # Try to process one item
            processed = process_queue_item(db)
            if not processed:
                # No more items in queue
                break
    except Exception as e:
        logger.exception(f"Error processing queue: {e}")


def google_search_processor():
    """Background thread that runs Google search periodically"""
    global running

    logger.info("Google search processor started")

    while running:
        try:
            logger.info("Running scheduled Google search...")
            db = SessionLocal()
            added_count = search_recent_douban_movies(db)
            logger.info(
                f"Scheduled Google search completed, added {added_count} items to queue"
            )
            db.close()
        except Exception as e:
            logger.exception(f"Error in scheduled Google search: {e}")

        # Wait for the configured interval before running the next search
        logger.info(
            f"Next Google search scheduled in {GOOGLE_SEARCH_INTERVAL_SECONDS} seconds"
        )

        # Sleep in smaller increments to check for shutdown request
        remaining_time = GOOGLE_SEARCH_INTERVAL_SECONDS
        while remaining_time > 0 and running:
            sleep_time = min(remaining_time, 10)  # Sleep max 10 seconds at a time
            time.sleep(sleep_time)
            remaining_time -= sleep_time


def start_scheduler():
    """Start the background scheduler threads"""
    global running, scheduler_thread, google_scheduler_thread

    # Start queue processor
    if scheduler_thread and scheduler_thread.is_alive():
        logger.warning("Queue processor is already running")
    else:
        running = True
        scheduler_thread = threading.Thread(target=queue_processor, daemon=True)
        scheduler_thread.start()
        logger.info("Queue processor started")

    # Start Google search scheduler
    if google_scheduler_thread and google_scheduler_thread.is_alive():
        logger.warning("Google search scheduler is already running")
    else:
        running = True
        google_scheduler_thread = threading.Thread(
            target=google_search_processor, daemon=True
        )
        google_scheduler_thread.start()
        logger.info(
            f"Google search scheduler started (interval: {GOOGLE_SEARCH_INTERVAL_SECONDS} seconds)"
        )


def stop_scheduler():
    """Stop the background scheduler threads"""
    global running

    if not (scheduler_thread and scheduler_thread.is_alive()) and not (
        google_scheduler_thread and google_scheduler_thread.is_alive()
    ):
        logger.warning("Schedulers are not running")
        return

    running = False
    logger.info("Schedulers stopping (may take up to 10 seconds to complete)")
