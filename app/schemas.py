from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ItemBase(BaseModel):
    douban_id: int
    imdb_id: Optional[str] = None
    title: str
    year: int
    rating: float
    update_time: datetime


class Item(ItemBase):
    class Config:
        orm_mode = True


class QueueBase(BaseModel):
    type: str
    id: str
    params: Optional[str] = None
    upsert_time: datetime


class Queue(QueueBase):
    class Config:
        orm_mode = True


class HistoryBase(BaseModel):
    change_id: int
    douban_id: int
    imdb_id: Optional[str] = None
    title: str
    year: int
    rating: float
    update_time: datetime


class History(HistoryBase):
    class Config:
        orm_mode = True
