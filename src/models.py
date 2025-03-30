from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
)
from .database import Base
from sqlalchemy import and_
import logging
from .utils import now_timestamp

logger = logging.getLogger(__name__)


class Item(Base):
    __tablename__ = "item"

    douban_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(16), index=True, nullable=True)
    douban_title = Column(String(128), index=True, nullable=True)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    raw_data = Column(Text, nullable=True)
    update_time = Column(Float, default=now_timestamp, nullable=True, index=True)


class Queue(Base):
    __tablename__ = "queue"

    type = Column(String(32), primary_key=True)
    id = Column(String(128), primary_key=True)
    params = Column(String(1024))
    upsert_time = Column(Float, default=now_timestamp, index=True)


class History(Base):
    __tablename__ = "history"

    change_id = Column(Integer, primary_key=True, autoincrement=True)
    douban_id = Column(Integer, nullable=False)
    imdb_id = Column(String(16), nullable=True)
    douban_title = Column(String(128), nullable=True)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    raw_data = Column(Text, nullable=True)
    update_time = Column(Float, nullable=True)


class Schedule(Base):
    __tablename__ = "schedule"

    type = Column(String(32), primary_key=True)  # Type of scheduled task
    next_run = Column(Float, nullable=False, index=True)  # When to run next


class List(Base):
    __tablename__ = "list"

    list_type = Column(String(32), primary_key=True)
    list_id = Column(String(128), primary_key=True)
    last_check_time = Column(Float, nullable=True)


def get_items(db, douban_id: int = None, imdb_id: str = None, douban_title: str = None):
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


def add_to_queue(db, item_type: str, item_id: str, params: str = None) -> bool:
    """
    Common method to add an item to the queue.
    For douban_id type, also tracks the ID in the item table.

    Args:
        db: Database session
        item_type: Type of queue item
        item_id: ID of the item
        params: Optional parameters

    Returns:
        bool: True if a new item was added to the queue, False if it already existed
    """
    # Convert douban_id to integer for item table tracking
    if item_type == "douban_id":
        try:
            douban_id_int = int(item_id)

            # Check if the douban_id exists in the item table
            existing_item = (
                db.query(Item).filter(Item.douban_id == douban_id_int).first()
            )

            if not existing_item:
                # Add to item table with minimal data
                minimal_item = Item(
                    douban_id=douban_id_int,
                    update_time=None,  # This indicates it's a placeholder
                )
                db.add(minimal_item)
                logger.debug(
                    f"Added Douban ID {douban_id_int} to item table as placeholder"
                )
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid douban_id format: {item_id}. Error: {e}")

    # Check if item is already in queue
    existing = db.query(Queue).filter_by(type=item_type, id=item_id).first()

    if not existing:
        # Add to queue
        queue_item = Queue(
            type=item_type,
            id=item_id,
            params=params,
            upsert_time=now_timestamp(),
        )
        db.add(queue_item)
        db.commit()
        logger.debug(f"Added item type={item_type}, id={item_id} to queue")
        return True
    else:
        # Only commit if we added to item table but not to queue
        if item_type == "douban_id":
            db.commit()
        return False
