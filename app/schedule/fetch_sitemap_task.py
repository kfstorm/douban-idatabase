import logging
from sqlalchemy.orm import Session

from app.info_provider.sitemap import fetch_sitemap_urls_from_sitemap_index
from app.schedule.base_task import BaseTask
from app.models import add_to_queue
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)


@register_task
class FetchSitemapTask(BaseTask):
    """Task to fetch sitemap URLs from Douban and add them to the queue"""

    @property
    def task_type(self) -> str:
        return "fetch_sitemap"

    @property
    def default_interval(self) -> int:
        # Run weekly (7 days)
        return 7 * 24 * 60 * 60

    def execute(self, db: Session) -> None:
        """
        Fetch sitemap index from Douban and add individual sitemaps to the queue
        """
        logger.info("Starting FetchSitemapTask")

        # Douban sitemap index URL
        sitemap_index_url = "https://www.douban.com/sitemap_index.xml"

        try:
            # Fetch sitemap URLs from the index
            sitemap_count = 0

            for sitemap_url in fetch_sitemap_urls_from_sitemap_index(sitemap_index_url):
                # Add to queue
                add_to_queue(db, "sitemap", sitemap_url)
                sitemap_count += 1

            logger.info(f"Added {sitemap_count} sitemap URLs to the queue")

        except Exception as e:
            logger.exception(f"Error fetching sitemap index: {e}")
            raise
