import logging
from urllib.parse import unquote, urlparse
import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.info_provider.google import google_search
from app.models import add_placeholder_tag
from app.utils import record_exception_metrics

logger = logging.getLogger(__name__)


# Constants
SEARCH_QUERY = "site:douban.com/tag inurl:doulist"


def discover_tags_by_google(db: Session, http_session: requests.Session):
    """
    Add tags by searching Google.
    """

    tag_names = set()  # Use a set to avoid duplicates

    for result in google_search(
        http_session,
        SEARCH_QUERY,
        max_results=settings.DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS,
    ):
        # Extract links and find tags
        url = result.get("link")
        if not url:
            continue
        parsed_url = urlparse(url)
        if not parsed_url.path.startswith("/tag/"):
            continue
        tag_name = unquote(parsed_url.path.split("/")[2])
        if not tag_name:
            continue
        tag_names.add(tag_name)

    logger.info(f"Found {len(tag_names)} tags")

    added_count = 0

    for tag_name in tag_names:
        try:
            if add_placeholder_tag(db, tag_name):
                added_count += 1
        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error adding tag {tag_name} as a placeholder: {e}")
            db.rollback()

    logger.info(f"Added {added_count} new tags as placeholders.")
