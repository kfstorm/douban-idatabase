import logging
import requests
from sqlalchemy.orm import Session

from app.http_utils import NoPermissionException
from app.info_provider.detail import (
    extract_douban_item_detail,
)
from app.info_provider.imdb import fetch_imdb_id
from app.info_provider.lists import get_list_api_by_list_type
from app.models import Item, List, Queue
from app.queue_processor.common import allow_update_item, merge_item, save_item_to_db
from app.utils import (
    now_timestamp,
    parse_douban_time,
    timestamp_to_local_time_str,
)

logger = logging.getLogger(__name__)


def process_list(
    db: Session, http_session: requests.Session, queue_item: Queue
) -> None:
    """
    Process a queue item of type 'subject_collection' or 'doulist'
    """
    list_type = queue_item.type
    list_id = queue_item.id
    logger.info(f"Processing list {list_type} {list_id} ...")
    list_api = get_list_api_by_list_type(http_session, list_type)

    # Check if we've processed this list before
    list_record = db.query(List).filter_by(list_type=list_type, list_id=list_id).first()

    try:
        # Get list info to check update time
        list_info = list_api.get_info(list_id)
    except NoPermissionException as e:
        logger.warning(
            f"List {list_type}/{list_id} is private or has no permission to access."
            f" {str(e)}"
        )
        if list_record:
            logger.info(f"Deleting list {list_type}/{list_id} record from database.")
            db.delete(list_record)
            db.commit()
        return

    # Look for update time field
    update_time_str = list_info.get("update_time") or list_info.get("updated_at")

    douban_update_time = None
    if update_time_str:
        douban_update_time = parse_douban_time(update_time_str)

    need_to_update_items = True
    need_to_update_douban_time = False

    # Skip fetching items if our last check is newer than the Douban update time
    if list_record and list_record.last_check_time and douban_update_time:
        if list_record.last_check_time >= douban_update_time:
            # Skip getting items if we've already checked after the list was updated
            need_to_update_items = False
            logger.info(
                f"Skipping list {list_type}/{list_id} items - our last check at "
                f"{timestamp_to_local_time_str(list_record.last_check_time)}"
                " is newer than Douban's update time "
                f"{timestamp_to_local_time_str(douban_update_time)}"
            )

        # Check if we need to update the douban_update_time field
        if list_record.douban_update_time != douban_update_time:
            need_to_update_douban_time = True
            logger.info(
                f"Updating Douban update time for list {list_type}/{list_id} from "
                f"{timestamp_to_local_time_str(list_record.douban_update_time) if list_record.douban_update_time else 'None'} to "  # noqa: B950
                f"{timestamp_to_local_time_str(douban_update_time)}"
            )

    # Only fetch and process list items if needed
    if need_to_update_items:
        # Fetch and process list items
        known_ids = set()

        # Process items in list
        for item in list_api.iter_items(list_id):
            detail_info = extract_douban_item_detail(item, f"{list_type}/{list_id}")
            if not detail_info:
                continue
            douban_id = detail_info["douban_id"]
            # Skip if already processed in this batch
            if douban_id in known_ids:
                continue
            known_ids.add(douban_id)

            existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
            if allow_update_item(existing_item):
                imdb_info = fetch_imdb_id(http_session, douban_id)
                if not imdb_info:
                    logger.warning(f"Failed to fetch IMDb ID for douban_id={douban_id}")
                    continue

                item = merge_item(detail_info, imdb_info)
                save_item_to_db(db, item)

        logger.info(f"Processed {len(known_ids)} items from list {list_type}/{list_id}")

    # Update or create list record with current check time
    # and douban update time if needed
    now = now_timestamp()
    if list_record:
        # Update last_check_time only if we actually processed items
        if need_to_update_items:
            list_record.last_check_time = now

        # Always update douban_update_time if different from what we have
        if need_to_update_douban_time:
            list_record.douban_update_time = douban_update_time

        if need_to_update_items or need_to_update_douban_time:
            db.commit()
            logger.info(
                f"Updated list record for {list_type}/{list_id}"
                + (
                    f", last_check_time to {timestamp_to_local_time_str(now)}"
                    if need_to_update_items
                    else ""
                )
                + (
                    f", douban_update_time to {timestamp_to_local_time_str(douban_update_time)}"  # noqa: B950
                    if need_to_update_douban_time
                    else ""
                )
            )
    else:
        # Create new list record
        list_record = List(
            list_type=list_type,
            list_id=list_id,
            last_check_time=now,
            douban_update_time=douban_update_time,
        )
        db.add(list_record)
        db.commit()
        logger.info(
            f"Created new list record for {list_type}/{list_id}"
            f", last_check_time={timestamp_to_local_time_str(now) if need_to_update_items else 'None'}"  # noqa: B950
            f", douban_update_time={timestamp_to_local_time_str(douban_update_time) if douban_update_time else 'None'}"  # noqa: B950
        )
