import logging
import re
from typing import Any, Dict, Iterator, List, Tuple
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse

from app.http_utils import get_json, get_response
from app.info_provider.common import COMMON_HEADERS
from app.info_provider.common import extract_douban_item_detail
from app.utils import ApplicationShutdownException, record_exception_metrics

logger = logging.getLogger(__name__)

# Base URLs for Douban type and rank APIs
CHART_PAGE_URL = "https://movie.douban.com/chart"
CHART_TOP_LIST_API_URL = "https://movie.douban.com/j/chart/top_list"

# Generate percentile intervals from 100% to 0% by steps of 10%
TYPE_RANK_INTERVALS = [f"{i}:{i-10}" for i in range(100, 0, -10)]


def get_types() -> List[Tuple[str, str]]:
    """
    Get available movie/TV types by crawling Douban chart page.

    Returns:
        List of tuples containing (type_name, type_id)
    """
    logger.info("Fetching movie/TV types from Douban chart page...")

    try:
        response = get_response(CHART_PAGE_URL, headers=COMMON_HEADERS)

        # Parse HTML content
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all <a> tags with links containing "typerank"
        type_links = soup.find_all("a", href=re.compile(r"/typerank\?"))

        result = []
        for link in type_links:
            href = link.get("href", "")
            # Parse the URL query parameters
            parsed_url = urlparse(href)
            query_params = parse_qs(parsed_url.query)

            # Extract type_name and type_id
            type_name = query_params.get("type_name", [""])[0]
            type_id = query_params.get("type", [""])[0]

            if type_name and type_id:
                result.append((type_name, type_id))

        # Remove duplicates while preserving order
        seen = set()
        unique_result = []
        for item in result:
            if item[1] not in seen:
                seen.add(item[1])
                unique_result.append(item)

        logger.info(
            f"Successfully fetched {len(unique_result)} movie/TV types from chart page"
        )
        return unique_result

    except ApplicationShutdownException:
        raise
    except Exception as e:
        record_exception_metrics(e)
        logger.error(f"Error fetching movie/TV types from chart page: {str(e)}")
        raise


def get_rank_details(
    type_id: str,
    interval_id: str,
    page_size: int = 100,
) -> Iterator[Dict[str, Any]]:
    """
    Get ranked movies/TV shows for a specific type and percentile interval.

    Args:

        type_id: The ID of the movie/TV type
        interval_id: Percentile range (e.g., "100:90" for top 10%, "90:80" for 10%-20%)

    Returns:
        Iterator of movie/TV details extracted from the rank data
    """
    logger.info(
        f"Fetching rank data for type_id={type_id}, percentile_range={interval_id}"
    )

    current_start = 0
    total_items = 0

    while True:
        params = {
            "type": type_id,
            "interval_id": interval_id,
            "start": current_start,
            "limit": page_size,
        }

        try:
            data = get_json(
                CHART_TOP_LIST_API_URL,
                params=params,
                headers=COMMON_HEADERS,
            )

            # The response is an array of items directly
            items = data if isinstance(data, list) else []
            page_item_count = len(items)

            logger.info(
                f"Found {page_item_count} items in rank for type_id={type_id}, "
                f"percentile_range={interval_id}, page start={current_start}"
            )

            # Stop pagination if no more items are returned
            if page_item_count == 0:
                break

            total_items += page_item_count

            for item in items:
                result = extract_douban_item_detail(
                    item,
                    f"{CHART_TOP_LIST_API_URL}?type={type_id}&interval_id={interval_id}",
                )
                if result:
                    yield result

            # Move to the next page
            current_start += page_size

        except ApplicationShutdownException:
            raise
        except Exception as e:
            record_exception_metrics(e)
            logger.error(f"Error fetching rank data: {str(e)}")
            raise

    logger.info(
        f"Finished fetching rank data for type_id={type_id}"
        f" and percentile_range={interval_id}. Total items: {total_items}"
    )
