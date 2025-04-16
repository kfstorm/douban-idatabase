from app.schedule.base_task import BaseTask
from app.metrics import update_db_metrics
import logging

from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)


@register_task
class UpdateDbMetricsTask(BaseTask):
    """Task to update database metrics statistics

    This scheduled task runs periodically to collect database statistics
    and store them in the DbStatistics table for fast metric querying.
    """

    @property
    def task_type(self) -> str:
        """Task type identifier"""
        return "update_db_metrics"

    @property
    def default_interval(self) -> int:
        """Default interval in seconds between task executions"""
        # Run hourly by default
        return 3600

    def execute(self, db):
        """
        Update database metrics statistics

        Collects statistics about the database (item counts, queue sizes, etc.)
        and stores them in the DbStatistics table for fast retrieval when
        metrics are queried via the /metrics endpoint.

        Args:
            db: Database session
        """
        update_db_metrics(db)
