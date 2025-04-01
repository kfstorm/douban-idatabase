import logging
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_

from app.models import Item, List, add_to_queue, Queue
from app.queue_processor.common import allow_update_item, allow_update_list
from app.utils import now_timestamp

logger = logging.getLogger(__name__)


def refresh(db: Session):
    """
    Periodically refresh data from item/list table by adding them back to the queue
    """

    logger.info("Starting refresh from item table...")

    last_print = now_timestamp()
    processed_items_count = 0
    added_items_count = 0

    # Query items not already in the queue
    items_query = (
        db.query(Item)
        .options(selectinload("*"))
        .outerjoin(Queue, and_(Queue.type == "douban_id", Queue.id == Item.douban_id))
        .filter(Queue.id == None)  # noqa: E711
    )

    all_items = items_query.all()
    for item in all_items:
        if allow_update_item(item):
            if add_to_queue(db, "douban_id", item.douban_id):
                added_items_count += 1
        processed_items_count += 1
        if now_timestamp() - last_print >= 60:
            logger.info(f"Processed {processed_items_count} items.")
            last_print = now_timestamp()

    logger.info(
        f"Added {added_items_count} items to queue for refresh."
        f" Processed {processed_items_count} items."
    )

    logger.info("Starting refresh from list table...")

    last_print = now_timestamp()
    processed_items_count = 0
    added_lists_count = 0

    # Query lists not already in the queue
    lists_query = (
        db.query(List)
        .options(selectinload("*"))
        .outerjoin(
            Queue,
            and_(Queue.type == List.list_type, Queue.id == List.list_id),
        )
        .filter(Queue.id == None)  # noqa: E711
    )

    all_lists = lists_query.all()
    for list_ in all_lists:
        if allow_update_list(list_):
            if add_to_queue(db, list_.list_type, list_.list_id):
                added_lists_count += 1
        processed_items_count += 1
        if now_timestamp() - last_print >= 60:
            logger.info(f"Processed {processed_items_count} lists.")
            last_print = now_timestamp()

    logger.info(
        f"Added {added_lists_count} lists to queue for refresh."
        f" Processed {processed_items_count} lists."
    )
