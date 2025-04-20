import logging
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
    Index,
)

from app.database import Base

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
    next_update_time = Column(
        Float, nullable=True, index=True
    )  # When the item can be updated next

    # Add composite index for faster metrics queries
    __table_args__ = (Index("idx_item_type_update_time", type, update_time),)


class Queue(Base):
    __tablename__ = "queue"

    type = Column(String(32), primary_key=True)
    id = Column(String(128), primary_key=True)
    params = Column(String(1024))
    upsert_time = Column(Float, index=True)

    # Add index for faster type-based counting
    __table_args__ = (Index("idx_queue_type", type),)


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    api_key = Column(String(64), unique=True, index=True, nullable=False)
    comment = Column(String(256), nullable=True)
    admin = Column(Boolean, nullable=False)
    rate_limit = Column(Integer, nullable=False)
    window_size = Column(Integer, nullable=False)
    create_time = Column(Float, nullable=False)
    disabled = Column(Boolean, nullable=False)


class History(Base):
    __tablename__ = "history"

    change_id = Column(Integer, primary_key=True, autoincrement=True)
    douban_id = Column(String(16), nullable=False, index=True)
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
    last_check_time = Column(Float, nullable=True, index=True)  # Add index
    douban_update_time = Column(Float, nullable=True)


class Tag(Base):
    __tablename__ = "tag"

    tag_name = Column(String(32), primary_key=True)
    fetch = Column(Boolean, nullable=True, index=True)  # Add index
    last_check_time = Column(Float, nullable=True, index=True)  # Add index

    # Add composite index for faster metrics queries
    __table_args__ = (Index("idx_tag_fetch_last_check", fetch, last_check_time),)


class Blacklist(Base):
    __tablename__ = "blacklist"

    type = Column(String(32), primary_key=True)
    id = Column(String(128), primary_key=True)
    count = Column(Integer, nullable=False)
    update_time = Column(Float, nullable=False)

    __table_args__ = (Index("idx_blacklist_type_id", type, id),)


class DbStatistics(Base):
    __tablename__ = "db_statistics"

    key = Column(String(64), primary_key=True)
    value = Column(Integer, nullable=False)
    update_time = Column(Float, nullable=False)


class ExploreConditions(Base):
    __tablename__ = "explore_conditions"

    conditions = Column(String(256), primary_key=True)
    total = Column(Integer, nullable=False)
    update_time = Column(Float, nullable=False)
