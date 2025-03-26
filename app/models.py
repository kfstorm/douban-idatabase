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


class Item(Base):
    __tablename__ = "item"

    douban_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(16), index=True)
    title = Column(String(128), index=True)
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
    title = Column(String(128))
    year = Column(Integer)
    rating = Column(Float)
    update_time = Column(DateTime)


def get_item_detail(db, douban_id: int = None, imdb_id: str = None):
    query = db.query(Item)
    if douban_id:
        query = query.filter(Item.douban_id == douban_id)
    elif imdb_id:
        query = query.filter(Item.imdb_id == imdb_id)

    return query.first()
