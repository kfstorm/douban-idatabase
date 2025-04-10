from typing import List, Optional

from app.http_utils import get_json
from app.info_provider.common import COMMON_HEADERS, extract_douban_item_detail
from app.info_provider.common import ITEM_TYPES


EXPLORE_URL = "https://m.douban.com/rexxar/api/v2/{}/recommend"


def explore(
    item_type: str,
    score_range: str,
    tags: Optional[List[str]] = None,
    count: int = 500,
) -> dict:
    """
    Fetch movie/tv recommendations from Douban based on the given score range and tags.
    Args:
        score_range (str): Score range for filtering movies/tvs.
        tags (List[str]): List of tags to filter movies/tvs.
        count (int): Number of items to fetch.

    Returns:
        dict: A dictionary containing the fetched items and total count.
    """
    if not item_type:
        raise ValueError("item_type must be provided")
    if item_type not in ITEM_TYPES:
        raise ValueError("item_type must be either 'movie' or 'tv'")

    url = EXPLORE_URL.format(item_type)
    tags_str = ",".join(tags) if tags else ""
    params = {
        "refresh": 0,
        "start": 0,
        "count": count,
        "uncollect": "false",
        "score_range": score_range,
        "tags": tags_str,
    }

    response = get_json(url, headers=COMMON_HEADERS, params=params)
    return {
        "items": [
            extract_douban_item_detail(
                item, f"explore:{item_type}:score_range:{score_range}/tags:{tags_str}"
            )
            for item in response["items"]
        ],
        "total": response["total"],
    }
