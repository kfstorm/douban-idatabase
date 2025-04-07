import logging
import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.info_provider.detail import fetch_douban_item_detail
from app.info_provider.imdb import fetch_imdb_id
from app.models import DeletedItem, Item, Queue
from app.queue_processor.common import allow_update_item, merge_item, save_item_to_db
from app.utils import now_timestamp, record_exception_metrics

logger = logging.getLogger(__name__)


def process_douban_id(
    db: Session, http_session: requests.Session, queue_item: Queue
) -> None:
    """
    Process a queue item of type 'douban_id'
    """
    if settings.DISABLE_INDIVIDUAL_ITEM_FETCH:
        return

    douban_id = queue_item.id

    # Check if item already exists and was updated within the refresh interval
    existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
    if not allow_update_item(existing_item):
        return

    # Fetch data from Douban and create Item object
    item = None
    try:
        item = _fetch_douban_item(http_session, douban_id)
    except requests.HTTPError as e:
        record_exception_metrics(e)
        if e.response.status_code == 404:
            # Item not found. It's possible that the item is not a movie or tv,
            # but we already added it to the item table.
            # It's also possible that the item was removed from Douban.
            # Delete the item from the item table.
            if existing_item:
                existing_deleted_item = (
                    db.query(DeletedItem)
                    .filter(DeletedItem.douban_id == existing_item.douban_id)
                    .first()
                )
                if not existing_deleted_item:
                    # Record the deletion in the deleted_item table
                    deleted_item = DeletedItem(
                        douban_id=existing_item.douban_id, delete_time=now_timestamp()
                    )
                    db.add(deleted_item)
                    logger.info(
                        f"Recorded deletion of douban_id={existing_item.douban_id}"
                        " in deleted_item table"
                    )

                # Now delete the item from the item table
                db.delete(existing_item)
                db.commit()

    if not item:
        logger.warning(f"Failed to fetch data for douban_id={douban_id}")
        return

    # Save the item to database
    save_item_to_db(db, item)

    logger.info(
        f"Successfully processed douban_id={douban_id}, title={item.douban_title}"
    )


def _fetch_douban_item(http_session: requests.Session, douban_id: str) -> Item:
    """
    Fetch movie data from Douban API and return an Item object
    """
    detail_info = fetch_douban_item_detail(http_session, douban_id)
    if not detail_info:
        return None
    if detail_info["in_blacklist"]:
        logging.warning(
            f"Douban ID {douban_id} is in blacklist. Skipping fetching IMDB ID."
        )
        imdb_info = {
            "imdb_id": None,
            "raw_data": {
                "imdb_id": None,
                "imdb_source": "in_blacklist",
            },
        }
    else:
        imdb_info = fetch_imdb_id(http_session, douban_id)
        if not imdb_info:
            return None
    logger.info(
        "Successfully fetched data"
        f" for douban_id={douban_id}: {detail_info['douban_title']}"
    )
    return merge_item(detail_info, imdb_info)
