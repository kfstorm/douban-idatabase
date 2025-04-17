from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Blacklist, Item, List, Queue, Tag, User, logger
from app.utils import now_timestamp


def get_items(
    db: Session, douban_id: str = None, imdb_id: str = None, douban_title: str = None
):
    query = db.query(Item)
    filters = []

    if douban_id:
        filters.append(Item.douban_id == douban_id)
    if imdb_id:
        filters.append(Item.imdb_id == imdb_id)
    if douban_title:
        # Use exact match for douban_title
        filters.append(Item.douban_title == douban_title)

    if filters:
        # Apply filters with AND logic between them
        query = query.filter(and_(*filters))

    return query.limit(5).all()


def add_placeholder_item(db: Session, douban_id: str) -> bool:
    """
    Add a placeholder item to the item table if it doesn't exist and is not blacklisted.

    Args:
        db: Database session
        douban_id: Douban ID of the item

    Returns:
        bool: True if a new item was added,
            False if it already existed or is blacklisted
    """
    # Check blacklist
    blacklist_entry = (
        db.query(Blacklist)
        .filter(Blacklist.type == "douban_id", Blacklist.id == douban_id)
        .first()
    )

    if blacklist_entry and blacklist_entry.count >= settings.BLACKLIST_THRESHOLD:
        if blacklist_entry.update_time + settings.BLACKLIST_DURATION >= now_timestamp():
            logger.info(f"Skipping placeholder for blacklisted douban_id {douban_id}")
            return False

    existing_item = db.query(Item).filter_by(douban_id=douban_id).first()

    if not existing_item:
        try:
            # Add to item table with minimal data
            minimal_item = Item(
                douban_id=douban_id,
                update_time=None,  # This indicates it's a placeholder
            )
            db.add(minimal_item)
            db.commit()

            from app.metrics import item_operations

            # Record the placeholder operation in metrics after successful commit
            item_operations.labels(type="unknown", operation="placeholder").inc()

            logger.info(f"Added placeholder item {douban_id}")
            return True
        except IntegrityError:
            # Another thread might have added the same item
            db.rollback()
            logger.info(f"Placeholder item {douban_id} already added by another thread")
            return False
    else:
        return False


def add_placeholder_list(db: Session, list_type: str, list_id: str) -> bool:
    """
    Add a placeholder list to the list table if it doesn't exist.

    Args:
        db: Database session
        list_type: Type of the list (e.g., 'subject_collection', 'doulist')
        list_id: ID of the list

    Returns:
        bool: True if a new list was added, False if it already existed
    """
    existing_list = (
        db.query(List).filter_by(list_type=list_type, list_id=list_id).first()
    )

    if not existing_list:
        try:
            # Add to list table with minimal data
            minimal_list = List(
                list_type=list_type,
                list_id=list_id,
                last_check_time=None,  # This indicates it's a placeholder
                douban_update_time=None,
            )
            db.add(minimal_list)
            db.commit()
            logger.info(f"Added placeholder list {list_type}/{list_id}")
            return True
        except IntegrityError:
            # Another thread might have added the same list
            db.rollback()
            logger.info(
                f"Placeholder list {list_type}/{list_id}"
                " already added by another thread"
            )
            return False
    else:
        return False


def add_placeholder_tag(db: Session, tag_name: str) -> bool:
    """
    Add a placeholder tag to the tag table if it doesn't exist.

    Args:
        db: Database session
        tag_name: Name of the tag

    Returns:
        bool: True if a new tag was added, False if it already existed
    """
    existing_tag = db.query(Tag).filter_by(tag_name=tag_name).first()

    if not existing_tag:
        try:
            # Add to tag table with minimal data
            minimal_tag = Tag(
                tag_name=tag_name,
                fetch=None,
                last_check_time=None,  # This indicates it's a placeholder
            )
            db.add(minimal_tag)
            db.commit()
            logger.info(f"Added placeholder tag {tag_name}")
            return True
        except IntegrityError:
            # Another thread might have added the same tag
            db.rollback()
            logger.info(f"Placeholder tag {tag_name} already added by another thread")
            return False
    else:
        return False


def add_to_queue(
    db: Session, queue_type: str, item_id: str, params: str = None
) -> bool:
    """
    Add an item to the queue if it doesn't exist

    Args:
        db: Database session
        queue_type: Type of queue item (e.g., 'douban_id', 'sitemap')
        item_id: ID of the item
        params: Optional parameters for the queue item

    Returns:
        bool: True if a new queue item was added, False if it already existed
    """
    existing_item = (
        db.query(Queue).filter(Queue.type == queue_type, Queue.id == item_id).first()
    )

    if not existing_item:
        try:
            queue_item = Queue(
                type=queue_type, id=item_id, params=params, upsert_time=now_timestamp()
            )
            db.add(queue_item)
            db.commit()
            logger.info(f"Added {queue_type} item to queue: {item_id}")
            return True
        except IntegrityError:
            # Another thread might have added the same queue item
            db.rollback()
            logger.info(
                f"Queue item {queue_type}/{item_id} already added by another thread"
            )
            return False
    return False


def get_user_by_api_key(db: Session, api_key: str):
    """
    Get a user by their API key

    Args:
        db: Database session
        api_key: The API key to look up

    Returns:
        User object if found, None otherwise
    """
    return db.query(User).filter(User.api_key == api_key).first()
