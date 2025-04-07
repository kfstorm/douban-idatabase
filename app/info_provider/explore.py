from typing import List, Optional

from app.http_utils import get_json
from app.info_provider.common import COMMON_HEADERS, extract_douban_item_detail


EXPLORE_URL = "https://m.douban.com/rexxar/api/v2/movie/recommend"

SCORE_RANGES = [f"{i},{i+1}" for i in range(0, 10)]


def get_explore_id(score_range: str, tags_str: str):
    return f"score_range:{score_range}/tags:{tags_str}"


def explore(
    score_range: str,
    tags: Optional[List[str]] = None,
    count: int = 500,
) -> dict:
    """
    Fetch movie recommendations from Douban based on the given score range and tags.
    Args:
        score_range (str): Score range for filtering movies.
        tags (List[str]): List of tags to filter movies.
        count (int): Number of items to fetch.

    Returns:
        dict: A dictionary containing the fetched items and total count.
    """
    tags_str = ",".join(tags) if tags else ""
    params = {
        "refresh": 0,
        "start": 0,
        "count": count,
        "uncollect": "false",
        "score_range": score_range,
        "tags": tags_str,
    }

    response = get_json(EXPLORE_URL, headers=COMMON_HEADERS, params=params)
    return {
        "items": [
            extract_douban_item_detail(
                item, "explore:" + get_explore_id(score_range, tags_str)
            )
            for item in response["items"]
        ],
        "total": response["total"],
    }
