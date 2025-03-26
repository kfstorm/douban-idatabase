from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db, init_db

app = FastAPI()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/item", response_model=List[schemas.Item])
def get_items(
    douban_id: int = Query(None),
    imdb_id: str = Query(None),
    douban_title: str = Query(None),
    db: Session = Depends(get_db),
):
    if not any([douban_id, imdb_id, douban_title]):
        raise HTTPException(
            status_code=400,
            detail="At least one of douban_id, imdb_id, or douban_title must be provided",
        )

    items = models.get_items(db, douban_id, imdb_id, douban_title)
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    return items
