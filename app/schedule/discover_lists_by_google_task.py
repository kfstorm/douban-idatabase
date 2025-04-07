import logging
from typing import Iterable, Optional
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.config import settings
from app.info_provider.google import google_search
from app.models import add_placeholder_list
from app.utils import record_exception_metrics
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)

# Constants
SEARCH_QUERY = "site:douban.com/doulist"


def extract_doulist_id_from_search_result(result: dict) -> Optional[str]:
    """Extract Doulist ID from a Google search result item.

    Args:
        result: A dictionary representing a single search result item

    Returns:
        The extracted Doulist ID or None if not found
    """
    url = result.get("link")
    if not url:
        return None
    parsed_url = urlparse(url)
    if not parsed_url.path.startswith("/doulist/"):
        return None

    id_part = parsed_url.path.split("/")[2]
    if not id_part:
        return None

    return id_part


@register_task
class DiscoverListsByGoogleTask(BaseTask):
    """Task to discover lists by searching Google"""

    @property
    def task_type(self) -> str:
        return "discover_lists_by_google"

    @property
    def default_interval(self) -> int:
        return 86400  # 1 day

    def search(self) -> Iterable[str]:
        """
        Search for doulists on Douban using Google.
        """
        yield from (
            google_search(
                SEARCH_QUERY,
                max_results=settings.DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS,
                extractor=extract_doulist_id_from_search_result,
            )
        )

    def execute(self, db: Session) -> None:
        """Add lists by searching Google."""
        added_count = 0
        for list_id in self.search():
            try:
                if add_placeholder_list(db, "doulist", list_id):
                    added_count += 1
            except Exception as e:
                record_exception_metrics(e)
                logger.error(f"Error adding doulist {list_id} as a placeholder: {e}")
                db.rollback()

        logger.info(f"Added {added_count} new list IDs as placeholders.")
