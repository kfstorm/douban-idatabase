import re
import time
import logging
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from .models import Queue
from urllib.parse import urlencode
from .config import settings
from .http import get_json

# Get logger instead of configuring it locally
logger = logging.getLogger(__name__)

# Constants
GOOGLE_SEARCH_URL = "https://www.google.com/search"
SEARCH_QUERY = "site:movie.douban.com/subject/ inurl:/subject/ -inurl:celebrities -inurl:discussion -inurl:photos -inurl:reviews -inurl:comments -inurl:episode -inurl:tv_discuss -inurl:doulists -inurl:cinema -inurl:trailer"
DOUBAN_ID_PATTERN = r"movie\.douban\.com/subject/(\d+)"

# ZenRows configuration
ZENROWS_API_URL = "https://serp.api.zenrows.com/v1/targets/google/search"


def search_recent_douban_movies(db: Session, http_session: requests.Session):
    """
    Search Google for recent Douban movie pages and add them to the queue.
    Continues to next page as long as there are more results.
    Uses ZenRows API via direct requests to bypass Google bot detection.

    Args:
        db: Database session
        http_session: HTTP session
    """
    # Check if ZenRows API key is configured
    if not settings.ZENROWS_API_KEY:
        logger.error(
            "ZenRows API key is not configured. Set ZENROWS_API_KEY environment variable."
        )
        return

    added_count = 0
    page = 0
    has_more_results = True

    while has_more_results:
        try:
            # Build the Google search URL with parameters
            google_params = {
                "q": SEARCH_QUERY,
                "tbs": "qdr:d",  # Native Google time filter: past day
                "start": page * 10,
            }

            # Build complete Google search URL
            google_url = f"{GOOGLE_SEARCH_URL}?{urlencode(google_params)}"

            # Define ZenRows API parameters
            zenrows_params = {
                "apikey": settings.ZENROWS_API_KEY,
                "url": google_url,
            }

            logger.info(f"Searching Google (page {page+1}) via ZenRows API...")

            # Make request to ZenRows API
            search_results = get_json(
                http_session, ZENROWS_API_URL, params=zenrows_params
            )

            # Check if we have organic results
            organic_results = search_results.get("organic_results", [])
            logger.info(
                f"Found {len(organic_results)} organic results on page {page+1}"
            )

            if not organic_results:
                logger.info("No organic results found, stopping pagination")
                has_more_results = False
                break

            # Extract links and find Douban IDs
            douban_ids = set()  # Use a set to avoid duplicates

            for result in organic_results:
                url = result.get("link", "")

                # Check if the URL matches the Douban pattern
                match = re.search(DOUBAN_ID_PATTERN, url)
                if match:
                    douban_id = match.group(1)
                    douban_ids.add(douban_id)

            logger.info(f"Found {len(douban_ids)} Douban IDs on page {page+1}")

            # Check if we found any Douban IDs on this page
            if not douban_ids:
                logger.info("No Douban IDs found on this page, stopping pagination")
                has_more_results = False
                break

            # Add all found Douban IDs to the queue
            for douban_id in douban_ids:
                try:
                    # Check if already in queue
                    existing = (
                        db.query(Queue)
                        .filter(Queue.type == "douban_id", Queue.id == douban_id)
                        .first()
                    )

                    if not existing:
                        # Add to queue
                        queue_item = Queue(
                            type="douban_id",
                            id=douban_id,
                            params=None,
                            upsert_time=datetime.utcnow(),
                        )
                        db.add(queue_item)
                        db.commit()
                        added_count += 1
                        logger.info(f"Added Douban ID {douban_id} to queue")
                except Exception as e:
                    logger.error(f"Error adding Douban ID {douban_id} to queue: {e}")
                    db.rollback()

            if douban_ids:
                # Move to the next page
                page += 1
            else:
                logger.info("No new Douban IDs found, stopping pagination")
                has_more_results = False

            # Be nice to ZenRows and Google (still important to rate limit)
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error during Google search via ZenRows API: {e}")
            has_more_results = False

    logger.info(f"Added {added_count} new Douban IDs to the queue")
    return
