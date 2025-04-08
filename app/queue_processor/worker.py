import logging
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from typing import List

from app.queue_processor.douban_id_processor import process_douban_id
from app.queue_processor.list_processor import process_list
from app.queue_processor.tag_processor import process_tag
from app.queue_processor.type_rank_processor import process_type_rank
from app.queue_processor.sitemap_processor import process_sitemap
from app.queue_processor.explore_processor import process_explore
from app.utils import (
    now_timestamp,
    record_exception_metrics,
)
from app.models import Queue
from app.config import settings
from app.database import SessionLocal
from app.http_utils import RateLimitException
from app.metrics import worker_processed_items, worker_processing_duration

logger = logging.getLogger(__name__)

# Track items currently being processed across all threads
processing_items = set()  # Set of (type, id) tuples


def process_single_queue_item(item_type: str, item_id: str) -> bool:
    """
    Process a single queue item in a separate thread.
    Retrieves the queue item from the database using its type and ID.
    Returns True if processed successfully, False otherwise.
    """
    # Use context manager for automatic session cleanup
    with SessionLocal() as db:
        # Fetch a fresh copy of the queue item in this session
        queue_item = (
            db.query(Queue).filter(Queue.type == item_type, Queue.id == item_id).first()
        )

        if not queue_item:
            logger.warning(f"Queue item not found: type={item_type}, id={item_id}")
            return False

        try:
            logger.info(f"Processing queue item: type={item_type}, id={item_id}")

            # Start timing for this specific item
            item_start_time = time.time()

            # Dispatch to appropriate handler based on queue item type
            if item_type == "douban_id":
                process_douban_id(db, queue_item)
            elif item_type == "subject_collection" or item_type == "doulist":
                process_list(db, queue_item)
            elif item_type == "tag":
                process_tag(db, queue_item)
            elif item_type == "type_rank":
                process_type_rank(db, queue_item)
            elif item_type == "sitemap":
                process_sitemap(db, queue_item)
            elif item_type == "explore":
                process_explore(db, queue_item)
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

            return True

        except RateLimitException as e:
            record_exception_metrics(e)
            db.rollback()
            worker_processed_items.labels(type=item_type, status="rate_limited").inc()
            # Don't propagate rate limit exceptions to allow other threads to continue
            logger.error(
                f"Rate limit hit while processing queue item {item_id}: {str(e)}"
            )
            return False

        except Exception as e:
            record_exception_metrics(e)
            db.rollback()
            logger.exception(
                f"Error processing queue item {queue_item.id}"
                f" of type {queue_item.type}: {e}"
            )
            # Record the error
            worker_processed_items.labels(type=item_type, status="error").inc()

            # Remove the item from queue even if there's an error
            db.delete(queue_item)
            db.commit()
            return True


def fetch_batch_of_queue_items(db: Session, batch_size: int) -> List[Queue]:
    """
    Fetch a batch of queue items to process.
    Excludes items that are currently being processed by other threads.
    """
    # Get a slightly larger batch to account for items we'll need to filter out
    items = (
        db.query(Queue)
        .order_by(Queue.upsert_time)
        .limit(batch_size + len(processing_items))
        .all()
    )

    # Filter out items that are already being processed
    available_items = [
        item for item in items if (item.type, item.id) not in processing_items
    ][:batch_size]

    return available_items


def process_queue_items(db: Session) -> None:
    """
    Process items from the queue using multiple threads until reaching time limit.
    Supports different types of queue items.
    """
    time_limit_seconds = settings.QUEUE_PROCESS_TIME_LIMIT_SECONDS
    thread_count = settings.QUEUE_PROCESSOR_THREAD_COUNT
    processed_count = 0

    # Record start time as timestamp
    start_time = now_timestamp()

    queue_size_before = db.query(Queue).count()
    if not queue_size_before:
        return

    # Log total queue size before processing
    logger.info(
        f"Starting queue processing with {queue_size_before} total items"
        f" in queue using {thread_count} threads"
    )

    # Create thread pool with named threads for better logging
    with ThreadPoolExecutor(
        max_workers=thread_count, thread_name_prefix="QueueWorker"
    ) as executor:
        # Keep track of active futures using composite key (type, id)
        futures = {}

        while True:
            # Check if we've exceeded the time limit
            elapsed_seconds = now_timestamp() - start_time
            if elapsed_seconds >= time_limit_seconds:
                logger.info(
                    f"Time limit reached ({time_limit_seconds} seconds)"
                    ", stopping processing"
                )
                break

            # Check for completed futures and process results
            done_future_keys = []
            for future_key, future in futures.items():
                if future.done():
                    done_future_keys.append(future_key)
                    try:
                        result = future.result()
                        if result:
                            processed_count += 1
                    except Exception as e:
                        item_type, item_id = future_key
                        logger.exception(
                            "Unhandled exception in worker thread"
                            f" for item type={item_type}, id={item_id}: {e}"
                        )
                    finally:
                        # Remove from processing items set
                        if future_key in processing_items:
                            processing_items.remove(future_key)

            # Remove completed futures
            for future_key in done_future_keys:
                futures.pop(future_key)

            # Calculate how many new tasks we can submit
            available_slots = thread_count - len(futures)

            if available_slots > 0:
                # Fetch new items to process
                queue_items = fetch_batch_of_queue_items(db, available_slots)

                if not queue_items:
                    # Queue is empty - if we also have no active futures, we're done
                    if not futures:
                        logger.info("Queue is empty, stopping processing")
                        break
                    else:
                        # We still have active futures, wait a bit for them to complete
                        time.sleep(0.1)
                        continue

                # Submit new items to the thread pool
                for item in queue_items:
                    # Use composite key (type, id) to track futures
                    future_key = (item.type, item.id)

                    # Mark this item as being processed
                    processing_items.add(future_key)

                    # Pass only the type and ID to the worker thread
                    futures[future_key] = executor.submit(
                        process_single_queue_item, item.type, item.id
                    )
            elif not futures:
                # No available slots and no active futures.
                # This shouldn't happen but let's handle it.
                logger.warning(
                    "No active futures and no available slots. This is unexpected"
                )
                break
            else:
                # No available slots but we have active futures.
                # wait a bit for some to complete
                time.sleep(0.1)

        # Wait for any remaining futures to complete
        if futures:
            logger.info(f"Waiting for {len(futures)} remaining tasks to complete...")
            for future_key, future in futures.items():
                try:
                    result = future.result()
                    if result:
                        processed_count += 1
                except Exception as e:
                    item_type, item_id = future_key
                    logger.exception(
                        "Unhandled exception in worker thread"
                        f" for item type={item_type}, id={item_id}: {e}"
                    )
            # Make sure to clear processing_items when done
            processing_items.clear()

    # Calculate total elapsed time
    total_elapsed_seconds = now_timestamp() - start_time

    if processed_count > 0:
        logger.info(
            f"Processed {processed_count} items from queue"
            f" in {total_elapsed_seconds:.2f} seconds using {thread_count} threads"
        )

    # Log remaining queue size after processing
    queue_size_after = db.query(Queue).count()
    logger.info(
        f"Queue processing completed. {queue_size_after} items remaining in queue"
    )
