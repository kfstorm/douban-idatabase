from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
)
from datetime import datetime
from .database import Base
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


class Item(Base):
    __tablename__ = "item"

    douban_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(16), index=True)
    douban_title = Column(String(128), index=True)
    year = Column(Integer)
    rating = Column(Float)
    raw_data = Column(Text, nullable=True)
    update_time = Column(DateTime, default=datetime.utcnow)


class Queue(Base):
    __tablename__ = "queue"

    type = Column(String(32), primary_key=True)
    id = Column(String(128), primary_key=True)
    params = Column(String(1024))
    upsert_time = Column(DateTime, default=datetime.utcnow, index=True)


class History(Base):
    __tablename__ = "history"

    change_id = Column(Integer, primary_key=True, autoincrement=True)
    douban_id = Column(Integer, nullable=False)
    imdb_id = Column(String(16))
    douban_title = Column(String(128))
    year = Column(Integer)
    rating = Column(Float)
    raw_data = Column(Text, nullable=True)
    update_time = Column(DateTime)


class Schedule(Base):
    __tablename__ = "schedule"

    type = Column(String(32), primary_key=True)  # Type of scheduled task
    next_run = Column(DateTime, nullable=False, index=True)  # When to run next


class KnownDoubanId(Base):
    __tablename__ = "known_douban_id"

    douban_id = Column(Integer, primary_key=True, index=True)
    discover_time = Column(DateTime, default=datetime.utcnow)


class List(Base):
    __tablename__ = "list"

    list_type = Column(String(32), primary_key=True)
    list_id = Column(String(128), primary_key=True)
    last_check_time = Column(DateTime, nullable=True)


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
    For douban_id type, also tracks the ID in known_douban_id table.

    Args:
        db: Database session
        item_type: Type of queue item
        item_id: ID of the item
        params: Optional parameters

    Returns:
        bool: True if a new item was added to the queue, False if it already existed
    """
    # Convert douban_id to integer for known_douban_id table
    if item_type == "douban_id":
        try:
            douban_id_int = int(item_id)

            # Check/insert into known_douban_id table
            known_id = (
                db.query(KnownDoubanId)
                .filter(KnownDoubanId.douban_id == douban_id_int)
                .first()
            )

            if not known_id:
                # Add to known_douban_id
                known_id = KnownDoubanId(
                    douban_id=douban_id_int, discover_time=datetime.utcnow()
                )
                db.add(known_id)
                logger.debug(
                    f"Added Douban ID {douban_id_int} to known_douban_id table"
                )
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid douban_id format: {item_id}. Error: {e}")

    # Check if item is already in queue
    existing = db.query(Queue).get((item_type, item_id))

    if not existing:
        # Add to queue
        queue_item = Queue(
            type=item_type,
            id=item_id,
            params=params,
            upsert_time=datetime.utcnow(),
        )
        db.add(queue_item)
        db.commit()
        logger.debug(f"Added item type={item_type}, id={item_id} to queue")
        return True
    else:
        # Only commit if we added to known_douban_id but not to queue
        if item_type == "douban_id":
            db.commit()
        return False
