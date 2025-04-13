import json
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.info_provider.detail import fetch_douban_item_detail
from app.info_provider.imdb import fetch_imdb_id
from app.models import Item, Queue
from app.queue_processor.common import (
    allow_update_item,
    merge_item,
    save_item_to_db,
    wrap_fetch_item,
)

logger = logging.getLogger(__name__)


def process_douban_id(db: Session, queue_item: Queue) -> None:
    """
    Process a queue item of type 'douban_id'
    """
    if settings.DISABLE_INDIVIDUAL_ITEM_FETCH:
        return

    douban_id = queue_item.id
    params = {}
    if queue_item.params:
        params = json.loads(queue_item.params)
    force = params.get("force", False)
    if not force:
        # Check if item already exists and was updated within the refresh interval
        existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
        if not allow_update_item(existing_item):
            return

    # Fetch data from Douban and create Item object
    item = wrap_fetch_item(db, douban_id, lambda: _fetch_douban_item(douban_id))

    if not item:
        logger.warning(f"Failed to fetch data for douban_id={douban_id}")
        return

    # Save the item to database
    save_item_to_db(db, item)

    logger.info(
        f"Successfully processed douban_id={douban_id}, title={item.douban_title}"
    )


def _fetch_douban_item(douban_id: str) -> Item:
    """
    Fetch movie data from Douban API and return an Item object
    """
    detail_info = fetch_douban_item_detail(douban_id)
    if not detail_info:
        return None
    imdb_info = fetch_imdb_id(douban_id, detail_info.get("in_blacklist"))
    if not imdb_info:
        return None
    logger.info(
        "Successfully fetched data"
        f" for douban_id={douban_id}: {detail_info['douban_title']}"
    )
    return merge_item(detail_info, imdb_info)
