from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
)
from app.database import Base
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


class Item(Base):
    __tablename__ = "item"

    douban_id = Column(String(16), primary_key=True, index=True)
    imdb_id = Column(String(16), index=True, nullable=True)
    douban_title = Column(String(128), index=True, nullable=True)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    type = Column(String(16), nullable=True, index=True)  # 'movie' or 'tv'
    raw_data = Column(Text, nullable=True)
    update_time = Column(Float, nullable=True, index=True)


class Queue(Base):
    __tablename__ = "queue"

    type = Column(String(32), primary_key=True)
    id = Column(String(128), primary_key=True)
    params = Column(String(1024))
    upsert_time = Column(Float, index=True)


class History(Base):
    __tablename__ = "history"

    change_id = Column(Integer, primary_key=True, autoincrement=True)
    douban_id = Column(String(16), nullable=False)
    imdb_id = Column(String(16), nullable=True)
    douban_title = Column(String(128), nullable=True)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    type = Column(String(16), nullable=True)  # 'movie' or 'tv'
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
    douban_update_time = Column(Float, nullable=True)


class Tag(Base):
    __tablename__ = "tag"

    tag_name = Column(String(32), primary_key=True)
    fetch = Column(Boolean, nullable=True)
    last_check_time = Column(Float, nullable=True)


class DeletedItem(Base):
    __tablename__ = "deleted_item"

    douban_id = Column(String(16), primary_key=True, index=True)
    delete_time = Column(Float, index=True)


def get_items(db, douban_id: str = None, imdb_id: str = None, douban_title: str = None):
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


def add_placeholder_item(db, douban_id: str) -> bool:
    """
    Add a placeholder item to the item table if it doesn't exist.

    Args:
        db: Database session
        douban_id: Douban ID of the item

    Returns:
        bool: True if a new item was added, False if it already existed
    """
    existing_item = db.query(Item).filter_by(douban_id=douban_id).first()

    if not existing_item:
        # Add to item table with minimal data
        minimal_item = Item(
            douban_id=douban_id,
            update_time=None,  # This indicates it's a placeholder
        )
        db.add(minimal_item)
        db.commit()
        logger.info(f"Added placeholder item {douban_id}")
        return True
    else:
        return False


def add_placeholder_list(db, list_type: str, list_id: str) -> bool:
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
    else:
        return False


def add_placeholder_tag(db, tag_name: str) -> bool:
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
    else:
        return False
