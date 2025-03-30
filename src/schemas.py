from pydantic import BaseModel
from typing import Optional


class ItemBase(BaseModel):
    douban_id: str
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
