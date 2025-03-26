from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from . import models, schemas
from .database import get_db, init_db

app = FastAPI()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/item", response_model=schemas.Item)
def get_item(
    douban_id: int = Query(None),
    imdb_id: str = Query(None),
    db: Session = Depends(get_db),
):
    if not douban_id and not imdb_id:
        raise HTTPException(
            status_code=400,
            detail="At least one of douban_id or imdb_id must be provided",
        )

    item = models.get_item_detail(db, douban_id, imdb_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item
