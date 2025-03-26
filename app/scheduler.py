import logging
import threading
import time
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal
from .worker import process_queue_item

logger = logging.getLogger(__name__)

# Flag to control the scheduler thread
running = False
scheduler_thread = None


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


def start_scheduler():
    """Start the background scheduler thread"""
    global running, scheduler_thread

    if scheduler_thread and scheduler_thread.is_alive():
        logger.warning("Scheduler is already running")
        return

    running = True
    scheduler_thread = threading.Thread(target=queue_processor, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the background scheduler thread"""
    global running

    if not scheduler_thread or not scheduler_thread.is_alive():
        logger.warning("Scheduler is not running")
        return

    running = False
    logger.info("Scheduler stopping (may take up to 10 seconds to complete)")
