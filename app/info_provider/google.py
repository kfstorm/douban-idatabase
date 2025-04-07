import logging
from typing import Any, Callable, Iterable, List
from urllib.parse import urlencode, parse_qs, urlparse
import time
import random
from bs4 import BeautifulSoup

from app.utils import record_exception_metrics
from app.config import settings
from app.http_utils import get_json, get_response

# Get logger instead of configuring it locally
logger = logging.getLogger(__name__)

# Constants
GOOGLE_SEARCH_URL = "https://www.google.com/search"
# ZenRows configuration
ZENROWS_API_URL = "https://serp.api.zenrows.com/v1/targets/google/search"

# User agents for direct search
# flake8: noqa: B950
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
]


def google_search(
    query: str,
    extractor: Callable[[dict], Any] = None,
    max_results: int = 100,
    **kwargs,
) -> Iterable[Any]:
    """
    Search Google.
    Continues to next page as long as there are more results.
    Uses ZenRows API if API key is configured, otherwise falls back to direct search.

    Args:
        query: Search query
        extractor: Function to extract data from each result
        max_results: Maximum number of results to return
        **kwargs: Additional search parameters
    """
    # Check if ZenRows API key is configured
    if settings.ZENROWS_API_KEY:
        yield from _zenrows_google_search(query, extractor, max_results, **kwargs)
    else:
        # Fall back to direct search without ZenRows
        yield from _direct_google_search(query, extractor, max_results, **kwargs)


def _zenrows_google_search(
    query: str,
    extractor: Callable[[dict], Any] = None,
    max_results: int = 100,
    **kwargs,
) -> Iterable[Any]:
    """
    Search Google using ZenRows API.

    Args:
        query: Search query
        extractor: Function to extract data from each result
        max_results: Maximum number of results to return
        **kwargs: Additional search parameters
    """
    count = 0
    has_more_results = True

    # Build the Google search URL with parameters
    google_params = {
        "q": query,
        **kwargs,
    }

    # Build complete Google search URL
    google_url = f"{GOOGLE_SEARCH_URL}?{urlencode(google_params)}"
    page = 0
    while has_more_results and count < max_results:
        page += 1
        try:
            # Define ZenRows API parameters
            zenrows_params = {
                "apikey": settings.ZENROWS_API_KEY,
                "url": google_url,
            }

            logger.info(f"Searching Google (page {page}) via ZenRows API...")

            # Make request to ZenRows API
            search_results = get_json(ZENROWS_API_URL, params=zenrows_params)

            # Check if we have organic results
            organic_results = search_results.get("organic_results", [])
            logger.info(f"Found {len(organic_results)} organic results on page {page}")

            if not organic_results:
                logger.info("No organic results found, stopping pagination")
                has_more_results = False
                break

            for result in organic_results:
                processed_result = extractor(result) if extractor else result
                if processed_result is not None:
                    yield processed_result
                    count += 1
                    if count >= max_results:
                        has_more_results = False
                        break

            if "pagination" in search_results:
                next_page = search_results["pagination"].get("next_page")
                if not next_page:
                    logger.info("No next page found, stopping pagination")
                    has_more_results = False
                    break
                google_url = next_page

        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error during Google search via ZenRows API: {e}")
            has_more_results = False


def _direct_google_search(
    query: str,
    extractor: Callable[[dict], Any] = None,
    max_results: int = 100,
    **kwargs,
) -> Iterable[Any]:
    """
    Search Google directly without using ZenRows.

    Args:
        query: Search query
        extractor: Function to extract data from each result
        max_results: Maximum number of results to return
        **kwargs: Additional search parameters
    """
    count = 0
    start = 0
    results_per_page = 10  # Google's default

    # Use a random user agent for each search to avoid detection
    user_agent = random.choice(USER_AGENTS)

    # Headers to mimic a browser request
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    while count < max_results:
        # Build search parameters
        search_params = {
            "q": query,
            "start": start,
            "num": results_per_page,
            **kwargs,
        }

        page = start // results_per_page + 1

        url = f"{GOOGLE_SEARCH_URL}?{urlencode(search_params)}"
        logger.info(f"Directly searching Google on page {page}...")

        try:
            # Add a delay to avoid rate limiting (be polite to Google)
            time.sleep(random.uniform(1.0, 3.0))

            # Make the request
            response = get_response(url, headers=headers)

            # Parse the HTML response
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract search results
            search_results = _extract_search_results_from_html(soup)

            if not search_results:
                logger.info("No more search results found or CAPTCHA encountered")
                break

            logger.info(f"Found {len(search_results)} results on page {page}")

            for result in search_results:
                processed_result = extractor(result) if extractor else result
                if processed_result is not None:
                    yield processed_result
                    count += 1
                    if count >= max_results:
                        break

            # Update start parameter for next page
            start += len(search_results)

            # Check if we've reached the end of results
            if len(search_results) < results_per_page:
                logger.info("End of search results reached")
                break

        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error during direct Google search: {e}")
            break


def _extract_search_results_from_html(soup: BeautifulSoup) -> List[dict]:
    """
    Extract search results from Google HTML response.

    Args:
        soup: BeautifulSoup object representing the Google search results page

    Returns:
        List of dictionaries containing search result information
    """
    results = []

    # Check for CAPTCHA
    if (
        "Our systems have detected unusual traffic" in soup.text
        or "If you're having trouble accessing Google Search" in soup.text
    ):
        logger.warning("Google CAPTCHA detected, cannot extract results")
        return results

    # Find all links that point to douban.com domains
    for link_element in soup.find_all("a"):
        try:
            href = link_element.get("href", "")

            # Process Google redirects if present
            if href.startswith("/url?"):
                parsed = urlparse(href)
                query_params = parse_qs(parsed.query)
                if "q" in query_params and query_params["q"]:
                    href = query_params["q"][0]

            # Skip if not a valid link or not a douban.com link
            if not href.startswith(("http://", "https://")):
                continue
            parsed_url = urlparse(href)
            if not parsed_url.netloc.endswith(".douban.com"):
                continue

            # Create result object
            result = {
                "link": href,
            }

            results.append(result)

        except Exception as e:
            logger.warning(f"Error extracting a search result: {e}")
            continue
    return results
