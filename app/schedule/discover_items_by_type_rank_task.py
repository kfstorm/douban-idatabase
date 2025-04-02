import logging
import requests
from sqlalchemy.orm import Session

from app.info_provider.type_rank import get_types, TYPE_RANK_INTERVALS
from app.models import Queue
from app.utils import now_timestamp

logger = logging.getLogger(__name__)


def discover_items_by_type_rank(db: Session, http_session: requests.Session):
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

            # Check if already in queue
            existing_queue_item = (
                db.query(Queue)
                .filter(Queue.type == "type_rank", Queue.id == queue_id)
                .first()
            )

            if not existing_queue_item:
                # Add to queue
                queue_item = Queue(
                    type="type_rank",
                    id=queue_id,
                    params=type_name,  # Store type name as params for reference
                    upsert_time=now_timestamp(),
                )
                db.add(queue_item)
                added_count += 1

    db.commit()
    logger.info(f"Added {added_count} type rank combinations to queue")
