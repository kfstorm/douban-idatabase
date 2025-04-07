import logging
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse
from sqlalchemy.orm import Session

from app.config import settings
from app.info_provider.google import google_search
from app.models import add_placeholder_tag
from app.utils import record_exception_metrics
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)

# Constants
SEARCH_QUERY = "site:douban.com/tag inurl:doulist"


def extract_douban_tag_name_from_search_result(result: dict) -> Optional[str]:
    """Extract Douban tag from a Google search result item.

    Args:
        result: A dictionary representing a single search result item

    Returns:
        The extracted Douban tag or None if not found
    """
    url = result.get("link")
    if not url:
        return None
    parsed_url = urlparse(url)
    if not parsed_url.path.startswith("/tag/"):
        return None

    tag_name = unquote(parsed_url.path.split("/")[2])
    if not tag_name:
        return None

    return tag_name


@register_task
class DiscoverTagsByGoogleTask(BaseTask):
    """Task to discover tags by searching Google"""

    @property
    def task_type(self) -> str:
        return "discover_tags_by_google"

    @property
    def default_interval(self) -> int:
        return 86400  # 1 day

    def search(self) -> Iterable[str]:
        """
        Search for tags on Douban using Google.
        """
        yield from (
            google_search(
                SEARCH_QUERY,
                extractor=extract_douban_tag_name_from_search_result,
                max_results=settings.DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS,
            )
        )

    def execute(self, db: Session) -> None:
        """Add tags by searching Google."""
        added_count = 0
        for tag_name in self.search():
            try:
                if add_placeholder_tag(db, tag_name):
                    added_count += 1
            except Exception as e:
                record_exception_metrics(e)
                logger.error(f"Error adding tag {tag_name} as a placeholder: {e}")
                db.rollback()

        logger.info(f"Added {added_count} new tags as placeholders.")
