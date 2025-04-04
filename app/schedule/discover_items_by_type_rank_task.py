import logging
import requests
from sqlalchemy.orm import Session

from app.info_provider.type_rank import get_types, TYPE_RANK_INTERVALS
from app.models import add_to_queue
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)


@register_task
class DiscoverItemsByTypeRankTask(BaseTask):
    """Task to discover items by type ranking"""

    @property
    def task_type(self) -> str:
        return "discover_items_by_type_rank"

    @property
    def default_interval(self) -> int:
        return 86400  # 1 day

    def execute(self, db: Session, http_session: requests.Session) -> None:
        """
        Discover items by type rank.
        Gets all available types and adds them to the queue with
        type='type_rank' and id='<type_id>/<interval_id>'.
        """
        logger.info("Starting discovery of items by type rank...")

        added_count = 0

        # Get all available types
        types = get_types(http_session)
        logger.info(f"Found {len(types)} types")

        # For each type and interval combination, add to queue
        for type_name, type_id in types:
            for interval_id in TYPE_RANK_INTERVALS:
                queue_id = f"{type_id}/{interval_id}"

                if add_to_queue(
                    db,
                    "type_rank",
                    queue_id,
                    type_name,  # Store type name as params for reference)
                ):
                    added_count += 1

        db.commit()
        logger.info(f"Added {added_count} type rank combinations to queue")
