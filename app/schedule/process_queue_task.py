import logging
from sqlalchemy.orm import Session

from app.queue_processor.worker import process_queue_items
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)


@register_task
class ProcessQueueTask(BaseTask):
    """Task to process items in the queue"""

    @property
    def task_type(self) -> str:
        return "process_queue"

    @property
    def default_interval(self) -> int:
        return 1  # 1 second

    def execute(self, db: Session) -> None:
        """
        Process items in the queue
        """
        process_queue_items(db)
