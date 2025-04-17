import logging
from sqlalchemy.orm import Session

from app.info_provider.type_rank import get_rank_details
from app.models import Queue
from app.queue_processor.common import try_to_save_item_to_db_with_detail

logger = logging.getLogger(__name__)


def process_type_rank(db: Session, queue_item: Queue) -> None:
    """
    Process a queue item of type 'type_rank'.
    Retrieves ranked items for a specific type and interval combination
    and adds them as complete items with IMDb data when possible.

    The queue_item.id format is expected to be "<type_id>/<interval_id>"
    """
    queue_id = queue_item.id
    type_name = queue_item.params  # Optional, used for logging

    logger.info(f"Processing type rank {queue_id} (type: {type_name})...")

    # Split the queue_id to get type_id and interval_id
    parts = queue_id.split("/")
    if len(parts) != 2:
        logger.error(f"Invalid type_rank queue id format: {queue_id}")
        return

    type_id, interval_id = parts

    added_count = 0
    total_count = 0
    # Get rank details for this type and interval
    for item_detail in get_rank_details(type_id, interval_id):
        douban_id = item_detail.get("douban_id")
        if not douban_id:
            continue
        total_count += 1

        if try_to_save_item_to_db_with_detail(db, item_detail):
            added_count += 1

    logger.info(
        f"Added/updated {added_count} items"
        f" for type rank {queue_id} (type: {type_name})."
        f" Total items processed: {total_count}"
    )
