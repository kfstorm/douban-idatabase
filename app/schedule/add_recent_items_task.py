import logging
import re
import requests
from sqlalchemy.orm import Session

from app.info_provider.google import google_search
from app.models import add_to_queue
from app.utils import record_exception_metrics

logger = logging.getLogger(__name__)


# Constants
SEARCH_QUERY = (
    "site:movie.douban.com/subject/"
    + " inurl:/subject/"
    + " -inurl:celebrities"
    + " -inurl:discussion"
    + " -inurl:photos"
    + " -inurl:reviews"
    + " -inurl:comments"
    + " -inurl:episode"
    + " -inurl:tv_discuss"
    + " -inurl:doulists"
    + " -inurl:cinema"
    + " -inurl:trailer"
)
DOUBAN_ID_PATTERN = r"movie\.douban\.com/subject/(\d+)"


def add_recent_items(db: Session, http_session: requests.Session):
    """
    Add recent items to the queue from Douban.
    This function searches for recent Douban movie pages
    """

    douban_ids = set()  # Use a set to avoid duplicates

    for result in google_search(
        http_session,
        SEARCH_QUERY,
        tbs="qdr:d",  # Native Google time filter: past day
    ):
        # Extract links and find Douban IDs
        url = result.get("link", "")

        # Check if the URL matches the Douban pattern
        match = re.search(DOUBAN_ID_PATTERN, url)
        if match:
            douban_id = match.group(1)
            douban_ids.add(douban_id)

    logger.info(f"Found {len(douban_ids)} Douban IDs")

    added_count = 0

    for douban_id in douban_ids:
        try:
            # Use common method to add to queue and item
            was_added = add_to_queue(db, "douban_id", douban_id)
            if was_added:
                added_count += 1
                logger.info(f"Added Douban ID {douban_id} to queue")
        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error adding Douban ID {douban_id} to queue: {e}")
            db.rollback()

    logger.info(f"Added {added_count} new Douban IDs to the queue")
    return
