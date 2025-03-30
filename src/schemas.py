from pydantic import BaseModel
from typing import Optional


class ItemBase(BaseModel):
    douban_id: int
    imdb_id: Optional[str] = None
    douban_title: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    # Not exposed in API responses
    # raw_data: Optional[str] = None
    update_time: Optional[float] = None


class Item(ItemBase):
    class Config:
        orm_mode = True


class QueueBase(BaseModel):
    type: str
    id: str
    params: Optional[str] = None
    upsert_time: float


class Queue(QueueBase):
    class Config:
        orm_mode = True


class HistoryBase(BaseModel):
    change_id: int
    douban_id: int
    imdb_id: Optional[str] = None
    douban_title: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    # Not exposed in API responses
    # raw_data: Optional[str] = None
    update_time: Optional[float] = None


class History(HistoryBase):
    class Config:
        orm_mode = True


class ScheduleBase(BaseModel):
    type: str
    next_run: float


class Schedule(ScheduleBase):
    class Config:
        orm_mode = True
