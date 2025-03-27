import csv
import logging
import os
import re
from urllib.parse import urlparse
import requests
import json
from datetime import datetime
from sqlalchemy.orm import Session

from .lists import CollectionApi, DoulistApi
from .models import Queue, Item, History, add_to_queue
from .config import settings
from .http import RateLimitException, get_response, get_json

logger = logging.getLogger(__name__)

# Updated Douban API URL for fetching movie details (mobile API)
DOUBAN_API_URL = "https://m.douban.com/rexxar/api/v2/movie/{}"
DOUBAN_IMDB_URL = "https://movie.douban.com/subject/{}/"
IMDB_ID_PATTERN = re.compile(r"IMDb:.*?(\btt\d+\b)")

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3",  # noqa: B950
    "Referer": "https://m.douban.com/movie",
}


def process_queue_items(db: Session, http_session: requests.Session) -> None:
    """
    Process items from the queue until reaching time limit (1 minute).
    Supports different types of queue items.
    """
    time_limit_seconds = settings.QUEUE_PROCESS_TIME_LIMIT_SECONDS
    processed_count = 0

    # Record start time
    start_time = datetime.utcnow()

    # Log total queue size before processing
    queue_size_before = db.query(Queue).count()
    logger.info(
        f"Starting queue processing with {queue_size_before} total items in queue"
    )

    while True:
        # Check if we've exceeded the time limit
        elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()
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

            # Dispatch to appropriate handler based on queue item type
            if item_type == "douban_id":
                process_douban_id(db, http_session, queue_item)
            elif item_type == "subject_collection" or item_type == "doulist":
                process_list(db, http_session, queue_item)
            else:
                logger.warning(f"Unsupported queue item type: {item_type}")
            # Remove the item from queue
            db.delete(queue_item)
            db.commit()

            processed_count += 1
        except RateLimitException as e:
            db.rollback()
            raise e

        except Exception as e:
            logger.exception(
                f"Error processing queue item {queue_item.id} of type {queue_item.type}: {e}"  # noqa: B950
            )
            # Remove the item from queue even if there's an error
            db.delete(queue_item)
            db.commit()
            processed_count += 1  # Count as processed even if there's an error
            # Continue with next item

    # Calculate total elapsed time
    total_elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()

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


def process_douban_id(
    db: Session, http_session: requests.Session, queue_item: Queue
) -> None:
    """
    Process a queue item of type 'douban_id'
    """
    douban_id = int(queue_item.id)

    # Check if item already exists and was updated within 1 day
    existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
    if existing_item and existing_item.update_time:
        time_diff = datetime.utcnow() - existing_item.update_time
        min_update_interval_days = settings.ITEM_REFRESH_INTERVAL_DAYS_DEFAULT * (
            (douban_id % 100) / 100 + 0.5
        )
        if time_diff.days < min_update_interval_days:
            logger.info(
                f"Skipping douban_id={douban_id},"
                f" already updated recently ({time_diff.days} days ago)."
                f" Min interval: {min_update_interval_days} days."
            )
            # Remove from queue since it's too recent to update
            db.delete(queue_item)
            db.commit()
            return

    # Fetch data from Douban and create Item object
    item = fetch_douban_item(http_session, douban_id)

    if not item:
        logger.warning(f"Failed to fetch data for douban_id={douban_id}")
        # Remove from queue even if failed (to avoid endless retries)
        db.delete(queue_item)
        db.commit()
        return

    # Save the item to database
    save_item_to_db(db, item)

    logger.info(
        f"Successfully processed douban_id={douban_id}, title={item.douban_title}"
    )


def process_list(
    db: Session, http_session: requests.Session, queue_item: Queue
) -> None:
    """
    Process a queue item of type 'subject_collection' or 'doulist'
    """
    list_type = queue_item.type
    list_id = queue_item.id
    logger.info(f"Processing list {list_type} {list_id} ...")
    collection_api = CollectionApi(http_session)
    doulist_api = DoulistApi(http_session)
    list_apis = {
        "subject_collection": collection_api,
        "doulist": doulist_api,
    }
    list_api = list_apis[list_type]
    items = list_api.get_items(list_id)
    known_ids = set()

    # Process items in list
    for item in items:
        parsed_url = urlparse(item["url"])
        douban_id = [_ for _ in parsed_url.path.split("/") if _][-1]

        # Skip if already processed in this batch
        if douban_id in known_ids:
            continue
        known_ids.add(douban_id)

        # Add to queue and known_douban_id table
        add_to_queue(db, "douban_id", douban_id)


def fetch_imdb_id_from_csv(douban_id: int) -> dict:
    if not settings.IDMB_CSV_PATH:
        return None
    if not os.path.exists(settings.IDMB_CSV_PATH):
        logger.warning(f"IMDb CSV file not found: {settings.IDMB_CSV_PATH}")
        return None
    with open(settings.IDMB_CSV_PATH, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if douban_id == int(row[0]):
                imdb_id = row[1]
                if not imdb_id:
                    imdb_id = None
                logger.info(
                    f"Found IMDb ID for douban_id={douban_id} in CSV."
                    f" IMDb ID: {imdb_id}"
                )
                return {
                    "imdb_id": imdb_id,
                    "raw_data": {
                        "imdb_id": imdb_id,
                        "imdb_source": os.path.basename(settings.IDMB_CSV_PATH),
                    },
                }
    return None


def fetch_imdb_id(http_session: requests.Session, douban_id: int) -> dict:
    """
    Fetch IMDb ID for a Douban movie using a simple web scraping method
    """
    result = fetch_imdb_id_from_csv(douban_id)
    if result:
        return result

    url = DOUBAN_IMDB_URL.format(douban_id)

    logger.info(f"Fetching IMDb ID for douban_id={douban_id}...")

    response = get_response(
        http_session, url, headers=COMMON_HEADERS, allow_redirects=True
    )

    imdb_id = None
    match = IMDB_ID_PATTERN.search(response.text)
    if match:
        imdb_id = match.group(1)
    logger.info(f"IMDb ID for douban_id={douban_id} is {imdb_id}.")

    return {
        "imdb_id": imdb_id,
        "raw_data": {
            "imdb_id": imdb_id,
            "imdb_source": url,
        },
    }


def fetch_douban_item_detail(http_session: requests.Session, douban_id: int) -> Item:
    """
    Fetch movie data from Douban Mobile API and return an Item object
    """
    # Construct the API URL with douban_id
    url = DOUBAN_API_URL.format(douban_id)

    # Make request with redirects enabled
    data = get_json(http_session, url, headers=COMMON_HEADERS, allow_redirects=True)

    # Extract relevant fields from the more detailed API response
    if not data or "id" not in data:
        logger.error(
            f"Invalid response from Douban API for douban_id={douban_id}: {data}"
        )
        return None

    # Check if the ID matches the requested douban_id
    if str(data["id"]) != str(douban_id):
        logger.error(
            f"ID mismatch in response from Douban API for douban_id={douban_id}: {data}"
        )
        return None

    title = data.get("title")

    # Try to extract year
    year = None
    if data.get("year"):
        try:
            year = int(data.get("year"))
        except (ValueError, TypeError):
            pass

    # Get rating
    rating = None
    if data.get("rating") and data["rating"].get("value"):
        try:
            rating = float(data["rating"]["value"])
        except (ValueError, TypeError):
            pass

    logger.info(f"Successfully fetched detail for douban_id={douban_id}: {title}")
    return {
        "douban_title": title,
        "year": year,
        "rating": rating,
        "raw_data": {
            "detail": data,
            "detail_source": url,
        },
    }


def fetch_douban_item(http_session: requests.Session, douban_id: int) -> Item:
    """
    Fetch movie data from Douban API and return an Item object
    """
    detail_info = fetch_douban_item_detail(http_session, douban_id)
    if not detail_info:
        logger.warning(f"Failed to fetch detail for douban_id={douban_id}")
        return None
    imdb_info = fetch_imdb_id(http_session, douban_id)
    if not imdb_info:
        logger.warning(f"Failed to fetch IMDb ID for douban_id={douban_id}")
        return None

    raw_data_obj = {
        **detail_info["raw_data"],
        **imdb_info["raw_data"],
    }

    # Create an Item object
    item = Item(
        douban_id=int(douban_id),
        imdb_id=imdb_info["imdb_id"],
        douban_title=detail_info["douban_title"],
        year=detail_info["year"],
        rating=detail_info["rating"],
        raw_data=json.dumps(raw_data_obj, ensure_ascii=False),
        update_time=datetime.utcnow(),
    )

    logger.info(
        f"Successfully fetched data for douban_id={douban_id}: {item.douban_title}"
    )
    return item


def save_item_to_db(db: Session, item: Item):
    """
    Save or update item in database and log history
    Now accepts an Item object directly instead of raw data
    """

    # Also add an entry to history
    history = History(
        douban_id=item.douban_id,
        imdb_id=item.imdb_id,
        douban_title=item.douban_title,
        year=item.year,
        rating=item.rating,
        update_time=item.update_time,
        raw_data=item.raw_data,
    )
    db.add(history)

    # Check if item already exists in database
    existing_item = db.query(Item).filter(Item.douban_id == item.douban_id).first()

    if existing_item:
        # Update the existing item with new values
        existing_item.douban_title = item.douban_title
        existing_item.year = item.year
        existing_item.rating = item.rating
        existing_item.update_time = item.update_time
        existing_item.imdb_id = item.imdb_id
        existing_item.raw_data = item.raw_data

        logger.info(
            f"Updated item: douban_id={item.douban_id}, title={item.douban_title}"
        )
    else:
        # Add the new item directly
        db.add(item)

        logger.info(
            f"Added new item: douban_id={item.douban_id}, title={item.douban_title}"
        )

    db.commit()
