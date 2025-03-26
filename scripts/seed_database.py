import sys
import os
import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import Item
from app.database import Base, engine
from app.logging_config import setup_logging

# Setup logging
logger = setup_logging()


def seed_database():
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if we already have items
    existing_count = session.query(Item).count()
    if existing_count > 0:
        logger.info(f"Database already contains {existing_count} items. Skipping seed.")
        return

    # Sample movie data with Chinese titles
    movies = [
        {
            "douban_id": 1291546,
            "imdb_id": "tt0111161",
            "douban_title": "肖申克的救赎",
            "year": 1994,
            "rating": 9.7,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1291561,
            "imdb_id": "tt0068646",
            "douban_title": "教父",
            "year": 1972,
            "rating": 9.3,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1295644,
            "imdb_id": "tt0468569",
            "douban_title": "蝙蝠侠：黑暗骑士",
            "year": 2008,
            "rating": 9.1,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1292052,
            "imdb_id": "tt0108052",
            "douban_title": "辛德勒的名单",
            "year": 1993,
            "rating": 9.5,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1292720,
            "imdb_id": "tt0167260",
            "douban_title": "指环王：王者归来",
            "year": 2003,
            "rating": 9.2,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1292722,
            "imdb_id": "tt0080684",
            "douban_title": "星球大战：帝国反击战",
            "year": 1980,
            "rating": 8.8,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1291543,
            "imdb_id": "tt0073486",
            "douban_title": "飞越疯人院",
            "year": 1975,
            "rating": 9.1,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1889243,
            "imdb_id": "tt1375666",
            "douban_title": "盗梦空间",
            "year": 2010,
            "rating": 9.3,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 3541415,
            "imdb_id": "tt3659388",
            "douban_title": "火星救援",
            "year": 2015,
            "rating": 8.4,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 25986180,
            "imdb_id": "tt2582802",
            "douban_title": "爆裂鼓手",
            "year": 2014,
            "rating": 8.6,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1291549,
            "imdb_id": "tt0110912",
            "douban_title": "低俗小说",
            "year": 1994,
            "rating": 8.9,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1292001,
            "imdb_id": "tt0109830",
            "douban_title": "阿甘正传",
            "year": 1994,
            "rating": 9.5,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 3007773,
            "imdb_id": "tt0482571",
            "douban_title": "致命魔术",
            "year": 2006,
            "rating": 8.8,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 1308767,
            "imdb_id": "tt1130884",
            "douban_title": "禁闭岛",
            "year": 2010,
            "rating": 8.6,
            "update_time": datetime.datetime.utcnow(),
        },
        {
            "douban_id": 25662329,
            "imdb_id": "tt0816692",
            "douban_title": "星际穿越",
            "year": 2014,
            "rating": 9.2,
            "update_time": datetime.datetime.utcnow(),
        },
    ]

    # Insert the movies
    for movie_data in movies:
        movie = Item(**movie_data)
        session.add(movie)

    # Commit the changes
    session.commit()
    logger.info(f"Added {len(movies)} sample movies to the database.")
    session.close()


if __name__ == "__main__":
    seed_database()
