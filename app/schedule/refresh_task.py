import logging
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_

from app.config import settings
from app.models import Item, List, Queue, Tag
from app.queue_processor.common import (
    allow_update_item,
    allow_update_list,
    allow_update_tag,
)
from app.utils import now_timestamp

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def process_in_batches(db, base_query, batch_size, process_callback, entity_name):
    """
    Process database query results in batches to prevent OOM errors

    Args:
        db: Database session
        base_query: SQLAlchemy base query to paginate
        batch_size: Number of records to process per batch
        process_callback: Function to process each item,
            returns True if item was added to queue
        entity_name: Name of the entity being processed (for logging)

    Returns:
        Tuple of (total_processed, total_added)
    """
    last_print = now_timestamp()
    processed_count = 0
    added_count = 0

    # Process in batches
    offset = 0
    while True:
        # Get one batch
        batch = base_query.limit(batch_size).offset(offset).all()
        if not batch:
            break

        # Process the current batch
        for item in batch:
            if process_callback(item):
                added_count += 1
            processed_count += 1

            if now_timestamp() - last_print >= 60:
                logger.info(f"Processed {processed_count} {entity_name}.")
                last_print = now_timestamp()

        # Move to next page
        offset += batch_size

    return processed_count, added_count


def _add_to_queue(db, item_type: str, item_id: str, params: str = None) -> bool:
    """
    Common method to add an item to the queue.

    Args:
        db: Database session
        item_type: Type of queue item
        item_id: ID of the item
        params: Optional parameters

    Returns:
        bool: True if a new item was added to the queue, False if it already existed
    """
    # Add to queue
    queue_item = Queue(
        type=item_type,
        id=item_id,
        params=params,
        upsert_time=now_timestamp(),
    )
    db.add(queue_item)


def _refresh_items(db: Session):
    """
    Refresh data from item table by adding items back to the queue
    """
    logger.info("Starting refresh from item table...")

    # Base query for items not already in the queue
    items_base_query = (
        db.query(Item)
        .options(selectinload("*"))
        .outerjoin(Queue, and_(Queue.type == "douban_id", Queue.id == Item.douban_id))
        .filter(Queue.id == None)  # noqa: E711
    )

    # Process item callback
    def process_item(item: Item):
        if allow_update_item(item):
            return _add_to_queue(db, "douban_id", item.douban_id)
        return False

    processed_items_count, added_items_count = process_in_batches(
        db, items_base_query, BATCH_SIZE, process_item, "items"
    )

    db.commit()

    logger.info(
        f"Added {added_items_count} items to queue for refresh."
        f" Processed {processed_items_count} items."
    )


def _refresh_lists(db: Session):
    """
    Refresh data from list table by adding lists back to the queue
    """
    logger.info("Starting refresh from list table...")

    # Base query for lists not already in the queue
    lists_base_query = (
        db.query(List)
        .options(selectinload("*"))
        .outerjoin(
            Queue,
            and_(Queue.type == List.list_type, Queue.id == List.list_id),
        )
        .filter(Queue.id == None)  # noqa: E711
    )

    # Process list callback
    def process_list(list_: List):
        if allow_update_list(list_):
            return _add_to_queue(db, list_.list_type, list_.list_id)
        return False

    processed_lists_count, added_lists_count = process_in_batches(
        db, lists_base_query, BATCH_SIZE, process_list, "lists"
    )

    db.commit()

    logger.info(
        f"Added {added_lists_count} lists to queue for refresh."
        f" Processed {processed_lists_count} lists."
    )


def _refresh_tags(db: Session):
    """
    Refresh data from tag table by adding tags back to the queue
    """
    logger.info("Starting refresh from tag table...")

    # Base query for tags not already in the queue
    tags_base_query = (
        db.query(Tag)
        .options(selectinload("*"))
        .outerjoin(
            Queue,
            and_(Queue.type == "tag", Queue.id == Tag.tag_name),
        )
        .filter(Queue.id == None)  # noqa: E711
    )

    # Process tag callback
    def process_tag(tag: Tag):
        if allow_update_tag(tag):
            return _add_to_queue(db, "tag", tag.tag_name)
        return False

    processed_tags_count, added_tags_count = process_in_batches(
        db, tags_base_query, BATCH_SIZE, process_tag, "tags"
    )

    db.commit()

    logger.info(
        f"Added {added_tags_count} tags to queue for refresh."
        f" Processed {processed_tags_count} tags."
    )


def refresh(db: Session):
    """
    Periodically refresh data from item/list/tag table by adding them back to the queue
    """
    _refresh_tags(db)
    _refresh_lists(db)
    if not settings.DISABLE_INDIVIDUAL_ITEM_FETCH:
        _refresh_items(db)
