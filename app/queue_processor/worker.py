import logging
import requests
import time
from sqlalchemy.orm import Session

from app.queue_processor.douban_id_processor import process_douban_id
from app.queue_processor.list_processor import process_list
from app.utils import (
    now_timestamp,
    record_exception_metrics,
)
from app.models import Queue
from app.config import settings
from app.http_utils import RateLimitException
from app.metrics import worker_processed_items, worker_processing_duration

logger = logging.getLogger(__name__)


def process_queue_items(db: Session, http_session: requests.Session) -> None:
    """
    Process items from the queue until reaching time limit (1 minute).
    Supports different types of queue items.
    """
    time_limit_seconds = settings.QUEUE_PROCESS_TIME_LIMIT_SECONDS
    processed_count = 0

    # Record start time as timestamp
    start_time = now_timestamp()

    queue_size_before = db.query(Queue).count()
    if not queue_size_before:
        return

    # Log total queue size before processing
    logger.info(
        f"Starting queue processing with {queue_size_before} total items in queue"
    )

    while True:
        # Check if we've exceeded the time limit
        elapsed_seconds = now_timestamp() - start_time
        if elapsed_seconds >= time_limit_seconds:
            logger.info(
                f"Time limit reached ({time_limit_seconds} seconds)"
                ", stopping processing"
            )
            break

        # Get oldest item from queue (any type)
        queue_item = db.query(Queue).order_by(Queue.upsert_time).first()

        if not queue_item:
            # Queue is empty
            logger.info("Queue is empty, stopping processing")
            break

        try:
            # Process this queue item based on its type
            item_id = queue_item.id
            item_type = queue_item.type
            logger.info(f"Processing queue item: type={item_type}, id={item_id}")

            # Start timing for this specific item
            item_start_time = time.time()

            # Dispatch to appropriate handler based on queue item type
            if item_type == "douban_id":
                process_douban_id(db, http_session, queue_item)
            elif item_type == "subject_collection" or item_type == "doulist":
                process_list(db, http_session, queue_item)
            else:
                logger.warning(f"Unsupported queue item type: {item_type}")

            # Record processing duration
            processing_duration = time.time() - item_start_time
            worker_processing_duration.labels(type=item_type).observe(
                processing_duration
            )
            worker_processed_items.labels(type=item_type, status="success").inc()

            # Remove the item from queue
            db.delete(queue_item)
            db.commit()

            processed_count += 1
        except RateLimitException as e:
            record_exception_metrics(e)
            db.rollback()
            worker_processed_items.labels(type=item_type, status="rate_limited").inc()
            raise e

        except Exception as e:
            record_exception_metrics(e)
            db.rollback()
            logger.exception(
                f"Error processing queue item {queue_item.id} of type {queue_item.type}: {e}"  # noqa: B950
            )
            # Record the error
            worker_processed_items.labels(type=item_type, status="error").inc()

            # Remove the item from queue even if there's an error
            db.delete(queue_item)
            db.commit()
            processed_count += 1  # Count as processed even if there's an error
            # Continue with next item

    # Calculate total elapsed time
    total_elapsed_seconds = now_timestamp() - start_time

    if processed_count > 0:
        logger.info(
            f"Processed {processed_count} items from queue"
            f" in {total_elapsed_seconds:.2f} seconds"
        )

    # Log remaining queue size after processing
    queue_size_after = db.query(Queue).count()
    logger.info(
        f"Queue processing completed. {queue_size_after} items remaining in queue"
    )
