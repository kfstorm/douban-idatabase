import logging
from typing import Iterable, Optional
from urllib.parse import urlparse
import requests
from sqlalchemy.orm import Session

from app.info_provider.google import google_search
from app.models import add_placeholder_item
from app.utils import record_exception_metrics
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

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


def extract_douban_id_from_search_result(result: dict) -> Optional[str]:
    """Extract Douban ID from a Google search result item.

    Args:
        result: A dictionary representing a single search result item

    Returns:
        The extracted Douban ID or None if not found
    """
    url = result.get("link")
    if not url:
        return None
    parsed_url = urlparse(url)
    if not parsed_url.path.startswith("/subject/"):
        return None

    id_part = parsed_url.path.split("/")[2]
    if not id_part:
        return None

    return id_part


@register_task
class AddRecentItemsTask(BaseTask):
    """Task to add recent items by Google search"""

    @property
    def task_type(self) -> str:
        return "google_search"

    @property
    def default_interval(self) -> int:
        return 3600 * 4  # 4 hours

    def search(self, http_session: requests.Session) -> Iterable[str]:
        """
        Search for recent items on Douban using Google.
        """
        yield from (
            google_search(
                http_session,
                SEARCH_QUERY,
                tbs="qdr:d",  # Native Google time filter: past day,
                extractor=extract_douban_id_from_search_result,
            )
        )

    def execute(self, db: Session, http_session: requests.Session) -> None:
        """
        Add recent items to the queue from Douban.
        This function searches for recent Douban movie pages
        """
        added_count = 0
        for douban_id in self.search(http_session):
            try:
                if add_placeholder_item(db, douban_id):
                    added_count += 1
            except Exception as e:
                record_exception_metrics(e)
                logger.error(
                    f"Error adding Douban ID {douban_id} as a placeholder: {e}"
                )
                db.rollback()

        logger.info(f"Added {added_count} new Douban IDs as placeholders")
