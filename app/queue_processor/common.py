import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from requests.exceptions import HTTPError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.http_utils import NoPermissionException
from app.info_provider.imdb import fetch_imdb_id
from app.models import Blacklist, History, Item, List, Tag
from app.utils import now_timestamp

logger = logging.getLogger(__name__)


def fill_next_update_time(item: Item) -> None:
    """
    Calculate and set the next_update_time property on the item based on its properties.

    Args:
        item: The Item object to be updated
    """
    if not item.update_time:
        item.next_update_time = None
        return

    # Calculate the next update time based on the year and update time.
    # The closer the year is to the current year,
    # the more frequently it will be updated.
    year = item.year
    if year:
        now_year = datetime.now().year
        diff_year = abs(year - now_year)
        interval_seconds = (
            settings.ITEM_REFRESH_INTERVAL_DEFAULT_DAYS * 86400 * (diff_year + 1)
        )
    else:
        # If year is not available, use the average interval of two setting values.
        interval_seconds = (
            (
                settings.ITEM_REFRESH_INTERVAL_DEFAULT_DAYS
                + settings.ITEM_REFRESH_INTERVAL_MAX_DAYS
            )
            / 2
            * 86400
        )
    # The bias is a random value between 1 and 1.2
    bias = ((int)(item.douban_id) % 10000) / 10000 * 0.2 + 1
    interval_seconds *= bias
    interval_seconds = max(
        interval_seconds, settings.ITEM_REFRESH_INTERVAL_DEFAULT_DAYS * 86400
    )
    interval_seconds = min(
        interval_seconds,
        settings.ITEM_REFRESH_INTERVAL_MAX_DAYS * 86400,
    )

    item.next_update_time = item.update_time + interval_seconds


def allow_update_item(
    existing_item: Item, detail_info: Optional[Dict[str, Any]] = None
) -> bool:
    if existing_item and existing_item.next_update_time:
        if detail_info:
            if detail_info["douban_title"] != existing_item.douban_title:
                # If the title has changed, allow immediate update
                return True
            if detail_info["rating"] != existing_item.rating:
                # If the rating has changed, allow immediate update
                return True
            if detail_info["year"] != existing_item.year:
                # If the year has changed, allow immediate update
                return True
            if detail_info["type"] != existing_item.type:
                # If the type has changed, allow immediate update
                return True

        current_time = now_timestamp()
        if current_time < existing_item.next_update_time:
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


def allow_update_tag(existing_tag: Tag) -> bool:
    if existing_tag and existing_tag.last_check_time:
        current_time = now_timestamp()
        if (
            current_time - existing_tag.last_check_time
            < settings.TAG_REFRESH_INTERVAL_DAYS * 86400
        ):
            return False
        return existing_tag.fetch is None or existing_tag.fetch
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
        type=detail_info["type"],
        raw_data=json.dumps(raw_data_obj, ensure_ascii=False),
        update_time=now_timestamp(),
    )


def _update_existing_item_columns(
    existing_item: Item, new_item: Item, context: str = ""
):
    """
    Update an existing item with data from a new item

    Args:
        existing_item: The existing Item object in the database
        new_item: The new Item object with updated data
        context: Optional context for logging (e.g., "after integrity error")
    """
    existing_item.douban_title = new_item.douban_title
    existing_item.year = new_item.year
    existing_item.rating = new_item.rating
    existing_item.update_time = new_item.update_time
    existing_item.next_update_time = new_item.next_update_time
    existing_item.imdb_id = new_item.imdb_id
    existing_item.type = new_item.type
    existing_item.raw_data = new_item.raw_data

    log_context = f" {context}" if context else ""
    logger.info(
        f"Updated item{log_context}: "
        f"douban_id={new_item.douban_id}, title={new_item.douban_title}"
    )


def save_item_to_db(db: Session, item: Item):
    """
    Save or update item in database and log history
    Now accepts an Item object directly instead of raw data
    """

    # Calculate next_update_time
    fill_next_update_time(item)

    # Also add an entry to history
    history = History(
        douban_id=item.douban_id,
        imdb_id=item.imdb_id,
        douban_title=item.douban_title,
        year=item.year,
        rating=item.rating,
        type=item.type,
        update_time=item.update_time,
        raw_data=item.raw_data,
    )
    db.add(history)

    existing_blacklist_entry = (
        db.query(Blacklist)
        .filter(Blacklist.type == "douban_id", Blacklist.id == item.douban_id)
        .first()
    )

    if existing_blacklist_entry:
        # If the item is blacklisted, remove it from the blacklist
        db.delete(existing_blacklist_entry)
        logger.info(f"Removed item from blacklist: douban_id={item.douban_id}")

    # Check if item already exists in database
    existing_item = db.query(Item).filter(Item.douban_id == item.douban_id).first()

    if existing_item:
        # Update the existing item with new values
        _update_existing_item_columns(existing_item, item)
    else:
        try:
            # Add the new item directly
            db.add(item)
            logger.info(
                f"Added new item: douban_id={item.douban_id}, title={item.douban_title}"
            )
        except IntegrityError:
            # Another thread might have added the same item
            db.rollback()
            logger.info(
                f"Item {item.douban_id} already added"
                f" by another thread, updating instead"
            )

            # Re-add the history entry that was rolled back
            db.add(history)

            # Fetch the item that was added by another thread and update it
            existing_item = (
                db.query(Item).filter(Item.douban_id == item.douban_id).first()
            )
            if existing_item:
                _update_existing_item_columns(
                    existing_item, item, "after integrity error"
                )

    db.commit()


def _update_blacklist(db: Session, douban_id: str):
    # Increment blacklist counter
    blacklist_entry = (
        db.query(Blacklist)
        .filter(Blacklist.type == "douban_id", Blacklist.id == douban_id)
        .first()
    )

    if blacklist_entry:
        blacklist_entry.count += 1
        blacklist_entry.update_time = now_timestamp()
    else:
        blacklist_entry = Blacklist(
            type="douban_id",
            id=douban_id,
            count=1,
            update_time=now_timestamp(),
        )
        db.add(blacklist_entry)

    db.commit()

    # Check if counter exceeds threshold
    if blacklist_entry.count >= settings.BLACKLIST_THRESHOLD:
        existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
        if existing_item:
            db.delete(existing_item)
            db.commit()
            logger.info(f"Removed item for blacklisted douban_id {douban_id}")


def wrap_fetch_item(
    db: Session,
    douban_id: str,
    fetch_func: callable,
) -> Any:
    try:
        return fetch_func()
    except NoPermissionException:
        _update_blacklist(db, douban_id)
        raise
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            _update_blacklist(db, douban_id)
        raise


IMDB_ID_UPDATE_INTERVAL = 3 * 30 * 24 * 60 * 60  # 3 months


def try_to_save_item_to_db_with_detail(
    db: Session, detail_info: Dict[str, Any]
) -> bool:
    douban_id = detail_info["douban_id"]
    existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
    if not allow_update_item(existing_item, detail_info):
        return False

    existing_raw_data = (
        json.loads(existing_item.raw_data)
        if existing_item and existing_item.raw_data
        else None
    )
    existing_imdb_update_time = (
        (existing_raw_data.get("imdb_update_time") or existing_item.update_time)
        if existing_raw_data
        else None
    )
    if allow_update_item(existing_item, None):
        allow_update_imdb_id = True
    elif (
        not existing_imdb_update_time
        or existing_imdb_update_time + IMDB_ID_UPDATE_INTERVAL < now_timestamp()
    ):
        allow_update_imdb_id = True
    else:
        allow_update_imdb_id = False

    if not allow_update_imdb_id:
        existing_raw_data = json.loads(existing_item.raw_data)
        imdb_info = {
            "imdb_id": existing_raw_data.get("imdb_id"),
            "raw_data": {
                "imdb_id": existing_raw_data.get("imdb_id"),
                "imdb_source": existing_raw_data.get("imdb_source"),
                "imdb_update_time": existing_imdb_update_time,
            },
        }
    else:
        # Fetch IMDb data
        imdb_info = wrap_fetch_item(
            db,
            douban_id,
            lambda douban_id=douban_id, detail_info=detail_info: fetch_imdb_id(
                douban_id, detail_info.get("in_blacklist")
            ),
        )
        if not imdb_info:
            logger.warning(f"Failed to fetch IMDb ID for douban_id={douban_id}")
            return False

    # Merge item data and save to database
    item = merge_item(detail_info, imdb_info)
    save_item_to_db(db, item)

    return True
