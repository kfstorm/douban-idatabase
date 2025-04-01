import json
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.models import History, Item, List
from app.utils import now_timestamp

logger = logging.getLogger(__name__)


def allow_update_item(existing_item: Item) -> bool:
    if existing_item and existing_item.update_time:
        current_time = now_timestamp()
        min_update_interval_seconds = (
            settings.ITEM_REFRESH_INTERVAL_DAYS_DEFAULT
            * 86400
            * (((int)(existing_item.douban_id) % 10000) / 10000 + 0.5)
        )
        if current_time - existing_item.update_time < min_update_interval_seconds:
            return False
    return True


def allow_update_list(existing_list: List) -> bool:
    if existing_list and existing_list.last_check_time:
        current_time = now_timestamp()
        if existing_list.douban_update_time:
            next_check_time = existing_list.last_check_time + max(
                min(
                    existing_list.last_check_time - existing_list.douban_update_time,
                    settings.LIST_REFRESH_MAX_INTERVAL_DAYS * 86400,
                ),
                settings.LIST_REFRESH_MIN_INTERVAL_DAYS * 86400,
            )
        else:
            next_check_time = (
                existing_list.last_check_time
                + settings.LIST_REFRESH_MIN_INTERVAL_DAYS * 86400
            )
        if current_time < next_check_time:
            return False

    return True


def merge_item(detail_info: dict, imdb_info: dict) -> Item:
    raw_data_obj = {
        **detail_info["raw_data"],
        **imdb_info["raw_data"],
    }

    # Create an Item object
    return Item(
        douban_id=detail_info["douban_id"],
        imdb_id=imdb_info["imdb_id"],
        douban_title=detail_info["douban_title"],
        year=detail_info["year"],
        rating=detail_info["rating"],
        raw_data=json.dumps(raw_data_obj, ensure_ascii=False),
        update_time=now_timestamp(),
    )


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
