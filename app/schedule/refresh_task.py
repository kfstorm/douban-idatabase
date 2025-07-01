import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.model_utils import add_to_queue
from app.models import Item, List, Tag
from app.queue_processor.common import (
    allow_update_item,
    allow_update_list,
    allow_update_tag,
)
from app.utils import now_timestamp
from app.schedule.base_task import BaseTask
from app.schedule.task_registry import register_task

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


@register_task
class RefreshTask(BaseTask):
    """Task to refresh data by adding items back to the queue"""

    @property
    def task_type(self) -> str:
        return "refresh"

    @property
    def default_interval(self) -> int:
        return 4 * 60 * 60  # 4 hours

    def execute(self, db: Session) -> None:
        """
        Periodically refresh data from item/list/tag table
            by adding them back to the queue
        """
        if not settings.DISABLE_TAG_REFRESH:
            self._refresh_tags(db)
        if not settings.DISABLE_LIST_REFRESH:
            self._refresh_lists(db)
        if not settings.DISABLE_INDIVIDUAL_ITEM_FETCH:
            self._refresh_items(db)

    def _refresh_items(self, db: Session):
        """
        Refresh data from item table by adding items back to the queue
        """
        logger.info("Starting refresh from item table...")

        current_time = now_timestamp()

        # Base query for items not already in the queue
        # and whose next_update_time has passed or is NULL
        items_base_query = db.query(Item).filter(
            or_(
                Item.next_update_time <= current_time,
                Item.next_update_time == None,  # noqa: E711
            )
        )

        # Process item callback
        def process_item(item: Item):
            if allow_update_item(item):
                self._add_to_queue(db, "douban_id", item.douban_id)
                return True
            return False

        processed_items_count, added_items_count = self._process_in_batches(
            db, items_base_query, BATCH_SIZE, process_item, "items"
        )

        db.commit()

        logger.info(
            f"Added {added_items_count} items to queue for refresh."
            f" Processed {processed_items_count} items."
        )

    def _refresh_lists(self, db: Session):
        """
        Refresh data from list table by adding lists back to the queue
        """
        logger.info("Starting refresh from list table...")

        # Base query for lists not already in the queue
        lists_base_query = db.query(List)

        # Process list callback
        def process_list(list_: List):
            if allow_update_list(list_):
                self._add_to_queue(db, list_.list_type, list_.list_id)
                return True
            return False

        processed_lists_count, added_lists_count = self._process_in_batches(
            db, lists_base_query, BATCH_SIZE, process_list, "lists"
        )

        db.commit()

        logger.info(
            f"Added {added_lists_count} lists to queue for refresh."
            f" Processed {processed_lists_count} lists."
        )

    def _refresh_tags(self, db: Session):
        """
        Refresh data from tag table by adding tags back to the queue
        """
        logger.info("Starting refresh from tag table...")

        # Base query for tags not already in the queue
        tags_base_query = db.query(Tag)

        # Process tag callback
        def process_tag(tag: Tag):
            if allow_update_tag(tag):
                self._add_to_queue(db, "tag", tag.tag_name)
                return True
            return False

        processed_tags_count, added_tags_count = self._process_in_batches(
            db, tags_base_query, BATCH_SIZE, process_tag, "tags"
        )

        db.commit()

        logger.info(
            f"Added {added_tags_count} tags to queue for refresh."
            f" Processed {processed_tags_count} tags."
        )

    def _process_in_batches(
        self, db, base_query, batch_size, process_callback, entity_name
    ):
        """
        Process database query results in batches to prevent OOM errors
        """
        last_print = now_timestamp()
        processed_count = 0
        added_count = 0

        # Process in batches
        offset = 0
        while True:
            # Get one batch
            batch = base_query.limit(batch_size).offset(offset).all()
            if not batch:
                break

            # Process the current batch
            for item in batch:
                if process_callback(item):
                    added_count += 1
                processed_count += 1

                if now_timestamp() - last_print >= 60:
                    logger.info(f"Processed {processed_count} {entity_name}.")
                    last_print = now_timestamp()

            # Move to next page
            offset += batch_size

        return processed_count, added_count

    def _add_to_queue(self, db, item_type: str, item_id: str, params: str = None):
        """
        Common method to add an item to the queue.
        """
        add_to_queue(db, item_type, item_id, params)
