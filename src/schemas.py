from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ItemBase(BaseModel):
    douban_id: int
    imdb_id: Optional[str] = None
    douban_title: str
    year: Optional[int] = None
    rating: Optional[float] = None
    # Not exposed in API responses
    # raw_data: Optional[str] = None
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
    douban_title: str
    year: Optional[int] = None
    rating: Optional[float] = None
    # Not exposed in API responses
    # raw_data: Optional[str] = None
    update_time: datetime


class History(HistoryBase):
    class Config:
        orm_mode = True


class ScheduleBase(BaseModel):
    type: str
    next_run: datetime


class Schedule(ScheduleBase):
    class Config:
        orm_mode = True
