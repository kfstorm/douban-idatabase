import logging
from urllib.parse import urlparse
import requests
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


@register_task
class DiscoverListsByGoogleTask(BaseTask):
    """Task to discover lists by searching Google"""

    @property
    def task_type(self) -> str:
        return "discover_lists_by_google"

    @property
    def default_interval(self) -> int:
        return 86400  # 1 day

    def execute(self, db: Session, http_session: requests.Session) -> None:
        """Add lists by searching Google."""
        list_ids = set()  # Use a set to avoid duplicates

        for result in google_search(
            http_session,
            SEARCH_QUERY,
            max_results=settings.DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS,
        ):
            # Extract links and find doulist IDs
            url = result.get("link")
            if not url:
                continue
            parsed_url = urlparse(url)
            if not parsed_url.path.startswith("/doulist/"):
                continue
            list_id = parsed_url.path.split("/")[2]
            if not list_id:
                continue
            list_ids.add(list_id)

        logger.info(f"Found {len(list_ids)} doulist list IDs")

        added_count = 0

        for list_id in list_ids:
            try:
                if add_placeholder_list(db, "doulist", list_id):
                    added_count += 1
            except Exception as e:
                record_exception_metrics(e)
                logger.error(f"Error adding doulist {list_id} as a placeholder: {e}")
                db.rollback()

        logger.info(f"Added {added_count} new list IDs as placeholders.")
