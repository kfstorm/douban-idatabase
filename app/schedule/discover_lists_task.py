import logging
from sqlalchemy.orm import Session

from app.info_provider.lists import ListsApi
from app.model_utils import add_placeholder_list
from app.utils import now_timestamp, record_exception_metrics
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)


@register_task
class DiscoverListsTask(BaseTask):
    """Task to discover lists from Douban directly"""

    @property
    def task_type(self) -> str:
        return "bootstrap_lists"

    @property
    def default_interval(self) -> int:
        return 86400  # 1 day

    def execute(self, db: Session) -> None:
        logger.info("Discovering lists...")

        count = 0
        added_count = 0
        last_print = now_timestamp()
        lists_api = ListsApi()
        for list_type, list_id in lists_api.iter_lists():
            count += 1
            if list_type == "subject_collection" or list_type == "doulist":
                try:
                    if add_placeholder_list(db, list_type, list_id):
                        added_count += 1
                except Exception as e:
                    record_exception_metrics(e)
                    logger.error(
                        f"Error adding list {list_type}/{list_id} as a placeholder: {e}"
                    )
                    db.rollback()
            else:
                logger.warning(f"Unknown list type: {list_type}")
            if now_timestamp() - last_print >= 60:
                logger.info(f"Processed {count} lists.")
                last_print = now_timestamp()

        logger.info(
            f"Finished discovering lists. Total processed: {count}."
            f" Added: {added_count}."
        )
