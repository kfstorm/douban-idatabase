import logging
from sqlalchemy.orm import Session

from app.models import Item, add_to_queue

logger = logging.getLogger(__name__)


def refresh_from_known_douban_id(db: Session):
    """
    Periodically refresh data from item table by adding them back to the queue
    Processes all known IDs (no sampling)
    """
    logger.info("Starting refresh from item table...")

    # Get all known douban IDs from the item table
    known_ids = db.query(Item.douban_id).all()
    total_ids = len(known_ids)

    if total_ids == 0:
        logger.info("No Douban IDs found. Skipping refresh.")
        return

    logger.info(f"Found {total_ids} Douban IDs to refresh")

    # Add all IDs to queue
    added_count = 0
    for id_tuple in known_ids:
        douban_id = id_tuple[0]
        if add_to_queue(db, "douban_id", douban_id):
            added_count += 1

    logger.info(
        f"Added {added_count} out of {total_ids} Douban IDs to queue for refresh"
    )
