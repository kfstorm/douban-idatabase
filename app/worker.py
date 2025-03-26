import logging
import requests
import json
from datetime import datetime
from sqlalchemy.orm import Session
from .models import Queue, Item, History

logger = logging.getLogger(__name__)

# Updated Douban API URL for fetching movie details (mobile API)
DOUBAN_API_URL = "https://m.douban.com/rexxar/api/v2/movie/{}"


def process_queue_item(db: Session) -> bool:
    """
    Process one item from the queue.
    Returns True if an item was processed, False if queue was empty.
    """
    # Get oldest douban_id from queue
    queue_item = (
        db.query(Queue)
        .filter(Queue.type == "douban_id")
        .order_by(Queue.upsert_time)
        .first()
    )

    if not queue_item:
        # Queue is empty
        return False

    try:
        # Process this queue item
        douban_id = queue_item.id
        logger.info(f"Processing queue item: douban_id={douban_id}")

        # Fetch data from Douban and create Item object
        item = fetch_douban_item(douban_id)

        if not item:
            logger.warning(f"Failed to fetch data for douban_id={douban_id}")
            # Remove from queue even if failed (to avoid endless retries)
            db.delete(queue_item)
            db.commit()
            return True

        # Save the item to database
        save_item_to_db(db, item)

        # Remove from queue
        db.delete(queue_item)
        db.commit()

        logger.info(
            f"Successfully processed douban_id={douban_id}, title={item.douban_title}"
        )
        return True

    except Exception as e:
        logger.exception(f"Error processing queue item {queue_item.id}: {e}")
        db.rollback()
        return True  # Return True so the scheduler continues with next item


def fetch_douban_item(douban_id: int) -> Item:
    """
    Fetch movie data from Douban Mobile API and return an Item object
    """
    try:
        # Construct the API URL with douban_id
        url = DOUBAN_API_URL.format(douban_id)

        # Set proper headers including the required Referer
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Referer": "https://m.douban.com/movie",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        # Make request with redirects enabled
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()

        data = response.json()

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

        # Create an Item object
        item = Item(
            douban_id=int(douban_id),
            imdb_id=None,  # We'll extract this in future
            douban_title=title,
            year=year,
            rating=rating,
            update_time=datetime.utcnow(),
        )

        logger.info(f"Successfully fetched data for douban_id={douban_id}: {title}")
        return item

    except Exception as e:
        logger.exception(
            f"Error fetching data from Douban API for douban_id={douban_id}: {e}"
        )
        return None


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
