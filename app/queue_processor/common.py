import json
import logging
from datetime import datetime
from typing import Any, Dict
from requests.exceptions import HTTPError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.http_utils import NoPermissionException
from app.info_provider.imdb import fetch_imdb_id
from app.models import Blacklist, ExploreConditions, Item, List, Tag
from app.utils import now_timestamp
from app.metrics import item_operations

logger = logging.getLogger(__name__)


def apply_bias(base: float, douban_id: str) -> float:
    """
    Apply douban_id based bias to a base value for randomization.

    Args:
        base: The base value to apply bias to
        douban_id: The douban ID to calculate bias for

    Returns:
        Base value multiplied by bias (between 1.0 and 1.2)
    """
    bias = ((int)(douban_id) % 10000) / 10000 * 0.2 + 1
    return base * bias


def calculate_year_based_interval_seconds(
    year: int,
    base_interval_days: int,
    min_interval_days: int = None,
    max_interval_days: int = None,
    douban_id: str = None,
) -> int:
    """
    Calculate interval in seconds based on year distance from current year.

    The closer the year is to the current year, the shorter the interval.

    Args:
        year: The year to calculate interval for
        base_interval_days: Base interval in days
        min_interval_days: Minimum interval in days (optional)
        max_interval_days: Maximum interval in days (optional)
        douban_id: Douban ID for bias calculation (optional)

    Returns:
        Interval in seconds based on year distance, with optional douban_id bias
    """
    current_year = datetime.now().year
    year_distance = abs(year - current_year)
    interval_seconds = base_interval_days * 86400 * (year_distance + 1)

    # Apply min/max bounds if specified
    if min_interval_days is not None:
        interval_seconds = max(interval_seconds, min_interval_days * 86400)
    if max_interval_days is not None:
        interval_seconds = min(interval_seconds, max_interval_days * 86400)

    # Apply douban_id based bias if provided
    if douban_id is not None:
        interval_seconds = apply_bias(interval_seconds, douban_id)

    return interval_seconds


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
        interval_seconds = calculate_year_based_interval_seconds(
            year,
            settings.ITEM_REFRESH_INTERVAL_DEFAULT_DAYS,
            settings.ITEM_REFRESH_INTERVAL_DEFAULT_DAYS,
            settings.ITEM_REFRESH_INTERVAL_MAX_DAYS,
            item.douban_id,
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
        # Apply douban_id based bias for non-year cases
        interval_seconds = apply_bias(interval_seconds, item.douban_id)

    item.next_update_time = item.update_time + interval_seconds


def should_update_item(existing_item: Item) -> bool:
    if existing_item and existing_item.next_update_time:
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
    Save or update item in database
    Now accepts an Item object directly instead of raw data
    """
    # Track operation type for metrics - will only be used after successful commit
    is_update = False

    # Calculate next_update_time
    fill_next_update_time(item)

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
        # Count updating a placeholder item as an add operation instead of update.
        # A placeholder item doesn't have update_time set yet
        is_update = existing_item.update_time is not None

        # Update the existing item with new values
        _update_existing_item_columns(existing_item, item)
    else:
        try:
            # Add the new item directly
            db.add(item)
            logger.info(
                f"Added new item: douban_id={item.douban_id}, title={item.douban_title}"
            )
            # This is an add operation
            is_update = False
        except IntegrityError:
            # Another thread might have added the same item
            db.rollback()
            logger.info(
                f"Item {item.douban_id} already added"
                f" by another thread, updating instead"
            )

            # Fetch the item that was added by another thread and update it
            existing_item = (
                db.query(Item).filter(Item.douban_id == item.douban_id).first()
            )
            if existing_item:
                # Count updating a placeholder item as an add operation instead of
                # update.
                # A placeholder item doesn't have update_time set yet
                is_update = existing_item.update_time is not None

                _update_existing_item_columns(
                    existing_item, item, "after integrity error"
                )

    # Commit the transaction
    db.commit()

    # Only increment metrics after successful commit
    operation_type = "update" if is_update else "add"
    item_operations.labels(type=item.type or "unknown", operation=operation_type).inc()


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
            # Store the item type before deletion for metrics
            item_type = existing_item.type or "unknown"

            # Delete the item
            db.delete(existing_item)
            db.commit()

            # Record the delete operation in metrics after successful commit
            item_operations.labels(type=item_type, operation="delete").inc()

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


def try_to_save_item_to_db_with_detail(
    db: Session, detail_info: Dict[str, Any]
) -> bool:
    douban_id = detail_info["douban_id"]
    existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()

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
    if should_update_item(existing_item):
        allow_update_imdb_id = True
    elif not existing_imdb_update_time:
        allow_update_imdb_id = True
    else:
        # Calculate year-based interval for IMDB ID updates
        year = detail_info.get("year") or (
            existing_item.year if existing_item else None
        )
        if year:
            imdb_interval_seconds = calculate_year_based_interval_seconds(
                year,
                settings.IMDB_ID_BASE_INTERVAL_DAYS,
                settings.IMDB_ID_BASE_INTERVAL_DAYS,
                settings.IMDB_ID_MAX_INTERVAL_DAYS,
                douban_id,
            )
        else:
            # If year is not available, use the average of base and max intervals
            imdb_interval_seconds = (
                (
                    settings.IMDB_ID_BASE_INTERVAL_DAYS
                    + settings.IMDB_ID_MAX_INTERVAL_DAYS
                )
                / 2
                * 86400
            )
            # Apply douban_id based bias for non-year cases
            imdb_interval_seconds = apply_bias(imdb_interval_seconds, douban_id)

        allow_update_imdb_id = (
            existing_imdb_update_time + imdb_interval_seconds < now_timestamp()
        )

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


def encode_explore_conditions(conditions: Dict[str, str]) -> str:
    """
    Convert a dictionary of conditions to a conditions string.

    Args:
        conditions: Dictionary of condition key-value pairs

    Returns:
        A formatted conditions string in the format "key1:value1/key2:value2/..."
        with all keys sorted alphabetically
    """
    # Sort all keys alphabetically
    sorted_keys = sorted(conditions.keys())

    # Build parts with all keys in sorted order
    parts = [f"{key}:{conditions[key]}" for key in sorted_keys]

    return "/".join(parts)


def decode_explore_conditions(conditions_str: str) -> Dict[str, str]:
    """
    Parse an explore conditions string into a dictionary of conditions.

    Args:
        conditions_str: A string in the format "key1:value1/key2:value2/..."

    Returns:
        Dictionary of conditions key-value pairs
    """
    conditions = {}
    for condition in conditions_str.split("/"):
        if ":" in condition:
            key, value = condition.split(":", 1)
            conditions[key] = value
    return conditions


def allow_update_explore_conditions(db: Session, conditions_str: str) -> bool:
    """
    Determine if explore conditions should be processed.

    Args:
        db: Database session
        conditions: The explore conditions string

    Returns:
        Boolean indicating whether processing should proceed
    """
    # Check if conditions already exist in database
    existing_entry = (
        db.query(ExploreConditions)
        .filter(ExploreConditions.conditions == conditions_str)
        .first()
    )

    if existing_entry is None:
        # Conditions don't exist in DB yet
        return True

    # Parse the conditions
    conditions_dict = decode_explore_conditions(conditions_str)

    # Don't update conditions that have year specified
    if "year" not in conditions_dict:
        return True

    # Use distance-based interval calculation for year-based conditions
    year = int(conditions_dict["year"])
    year_based_interval = calculate_year_based_interval_seconds(
        year,
        settings.EXPLORE_CONDITIONS_BASE_INTERVAL_DAYS,
        settings.EXPLORE_CONDITIONS_BASE_INTERVAL_DAYS,
        settings.EXPLORE_CONDITIONS_MAX_INTERVAL_DAYS,
    )

    if existing_entry.update_time + year_based_interval > now_timestamp():
        return False

    # For score range `0,1`, apply additional minimum interval of 30 days
    if "score_range" in conditions_dict:
        score_range = conditions_dict["score_range"]
        if score_range == "0,1":
            min_update_interval = 30 * 24 * 60 * 60
            if existing_entry.update_time + min_update_interval > now_timestamp():
                return False

    return True
