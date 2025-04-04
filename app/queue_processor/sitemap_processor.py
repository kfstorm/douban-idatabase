import logging
import requests
from sqlalchemy.orm import Session

from app.models import Queue, add_placeholder_item
from app.info_provider.sitemap import fetch_douban_ids_from_sitemap

logger = logging.getLogger(__name__)


def process_sitemap(
    db: Session, http_session: requests.Session, queue_item: Queue
) -> None:
    """
    Process a queue item of type 'sitemap'

    Extracts Douban IDs from the sitemap and adds them as placeholder items
    """
    sitemap_url = queue_item.id  # The sitemap URL is stored in the id field

    logger.info(f"Processing sitemap: {sitemap_url}")

    # Fetch Douban IDs from the sitemap
    added_count = 0
    found_count = 0
    for douban_id in fetch_douban_ids_from_sitemap(http_session, sitemap_url):
        found_count += 1
        # Add as placeholder item if it doesn't exist
        if add_placeholder_item(db, douban_id):
            added_count += 1

            # Commit every 100 items to avoid large transactions
            if added_count % 100 == 0:
                db.commit()
                logger.info(
                    f"Added {added_count}/{found_count} placeholder items"
                    f" so far from {sitemap_url}"
                )

    # Final commit for remaining items
    db.commit()
    logger.info(
        f"Successfully added {added_count}/{found_count} placeholder items"
        f" from {sitemap_url}"
    )
