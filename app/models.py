from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
from sqlalchemy import and_


class Item(Base):
    __tablename__ = "item"

    douban_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(16), index=True)
    douban_title = Column(String(128), index=True)
    year = Column(Integer)
    rating = Column(Float)
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
    update_time = Column(DateTime)


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
