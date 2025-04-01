import logging
import requests

from app.utils import record_exception_metrics
from urllib.parse import urlencode
from app.config import settings
from app.http_utils import get_json

# Get logger instead of configuring it locally
logger = logging.getLogger(__name__)

# Constants
GOOGLE_SEARCH_URL = "https://www.google.com/search"
# ZenRows configuration
ZENROWS_API_URL = "https://serp.api.zenrows.com/v1/targets/google/search"


def google_search(
    http_session: requests.Session, query: str, max_results: int = 100, **kwargs
):
    """
    Search Google.
    Continues to next page as long as there are more results.
    Uses ZenRows API via direct requests to bypass Google bot detection.

    Args:
        http_session: HTTP session
        query: Search query
        max_results: Maximum number of results to return
    """
    # Check if ZenRows API key is configured
    if not settings.ZENROWS_API_KEY:
        logger.error(
            "ZenRows API key is not configured."
            + " Set ZENROWS_API_KEY environment variable."
        )
        return

    page = 0
    count = 0
    has_more_results = True

    while has_more_results and count < max_results:
        try:
            # Build the Google search URL with parameters
            google_params = {
                "q": query,
                **kwargs,
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

            for result in organic_results:
                yield result
                count += 1
                if count >= max_results:
                    has_more_results = False
                    break
            if organic_results:
                # Move to the next page
                page += 1
            else:
                logger.info("No more results found, stopping pagination")
                has_more_results = False

        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error during Google search via ZenRows API: {e}")
            has_more_results = False
