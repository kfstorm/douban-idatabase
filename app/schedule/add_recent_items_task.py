import logging
from urllib.parse import urlparse
import requests
from sqlalchemy.orm import Session

from app.info_provider.google import google_search
from app.models import add_placeholder_item
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
        url = result.get("link")
        if not url:
            continue
        parsed_url = urlparse(url)
        if not parsed_url.path.startswith("/subject/"):
            continue
        douban_id = parsed_url.path.split("/")[2]
        if not douban_id or not douban_id.isdecimal():
            continue
        douban_ids.add(douban_id)

    logger.info(f"Found {len(douban_ids)} Douban IDs")

    added_count = 0

    for douban_id in douban_ids:
        try:
            if add_placeholder_item(db, douban_id):
                added_count += 1
        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error adding Douban ID {douban_id} as a placeholder: {e}")
            db.rollback()

    logger.info(f"Added {added_count} new Douban IDs as placeholders")
    return
