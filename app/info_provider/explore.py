import logging
from typing import List, Optional, Dict, Any
import time

from app.http_utils import get_json
from app.info_provider.common import COMMON_HEADERS, extract_douban_item_detail
from app.info_provider.common import ITEM_TYPES

logger = logging.getLogger(__name__)


EXPLORE_URL = "https://m.douban.com/rexxar/api/v2/{}/recommend"
PAGE_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3
RETRY_DELAY = 3  # seconds


def explore(
    item_type: str,
    score_range: str,
    tags: Optional[List[str]] = None,
    max_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch movie/tv recommendations from Douban based on the given score range and tags.

    Args:
        item_type (str): Type of item to fetch ('movie' or 'tv').
        score_range (str): Score range for filtering movies/tvs.
        tags (List[str]): List of tags to filter movies/tvs.
        max_count (Optional[int]): Maximum number of items to fetch.
            If None, all available items will be fetched.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - items: List of fetched items
            - total: Total number of items available
    """
    if not item_type:
        raise ValueError("item_type must be provided")
    if item_type not in ITEM_TYPES:
        raise ValueError("item_type must be either 'movie' or 'tv'")

    url = EXPLORE_URL.format(item_type)
    tags_str = ",".join(tags) if tags else ""
    source_context = f"explore:{item_type}:score_range:{score_range}/tags:{tags_str}"

    total = None
    fetched_count = 0
    consecutive_failures = 0
    result_items = []

    while (max_count is None or fetched_count < max_count) and (
        total is None or fetched_count < total
    ):
        # Calculate how many items to request in this batch
        current_page_size = PAGE_SIZE
        if max_count is not None:
            current_page_size = min(PAGE_SIZE, max_count - fetched_count)
            if current_page_size <= 0:
                break

        params = {
            "refresh": 0,
            "start": fetched_count,
            "count": current_page_size,
            "uncollect": "false",
            "score_range": score_range,
            "tags": tags_str,
        }

        response = get_json(url, headers=COMMON_HEADERS, params=params)
        items = response.get("items", [])

        if total is None:
            total = response.get("total", 0)

        if fetched_count >= total:
            # All items fetched, break the loop
            break

        if not items:
            # No items returned, count as a failure
            logger.warning(
                f"Received empty response for {source_context}"
                f" with start={fetched_count}, count={current_page_size}, total={total}"
            )
            consecutive_failures += 1

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                # Too many consecutive failures, abort
                logger.error(
                    f"Too many consecutive failures for {source_context}"
                    f" with start={fetched_count}, count={current_page_size}"
                    f", total={total}"
                )
                break

            # Wait before retrying
            time.sleep(RETRY_DELAY)
            continue
        elif fetched_count + len(items) < total and len(items) < current_page_size:
            logger.warning(
                f"Received fewer items than requested for {source_context}"
                f" with start={fetched_count}, count={current_page_size},"
                f" total={total}. Received: {len(items)}"
            )

        # Successfully got some items, reset the failure counter
        consecutive_failures = 0

        # Process the items
        for item in items:
            result_items.append(extract_douban_item_detail(item, source_context))

        fetched_count += len(items)

    return {"items": result_items, "total": total or 0}
