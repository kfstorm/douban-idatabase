import logging
from sqlalchemy.orm import Session

from app.models import add_to_queue
from app.queue_processor.explore_processor import SCORE_RANGES
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task
from app.queue_processor.explore_processor import encode_explore_queue_id

logger = logging.getLogger(__name__)


@register_task
class DiscoverItemsByExploreTask(BaseTask):
    """Task to discover items by exploring Douban based on score ranges"""

    @property
    def task_type(self) -> str:
        return "discover_items_by_explore"

    @property
    def default_interval(self) -> int:
        # Run weekly (7 days)
        return 7 * 24 * 60 * 60

    def execute(self, db: Session) -> None:
        """
        Add queue items for each score range to explore Douban items.
        """
        logger.info("Starting discovery of items by explore...")

        added_count = 0
        for score_range in SCORE_RANGES:
            # Create queue ID using the helper function
            queue_id = encode_explore_queue_id({"score_range": score_range})

            # Add to queue
            if add_to_queue(db, "explore", queue_id):
                added_count += 1
                logger.info(f"Added explore queue item: {queue_id}")

        logger.info(f"Added {added_count} explore queue items")
