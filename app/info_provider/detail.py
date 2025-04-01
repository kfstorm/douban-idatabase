import logging
from urllib.parse import urlparse
import requests

from app.http_utils import get_json
from app.info_provider.common import COMMON_HEADERS

logger = logging.getLogger(__name__)

DOUBAN_REXXAR_API_URL = "https://m.douban.com/rexxar/api/v2/movie/{}"


def extract_douban_item_detail(item: dict, source: str) -> dict:
    """
    Extract relevant fields from a Douban item detail response
    """
    if item["type"] not in ["movie", "tv"]:
        return None

    # Try to extract Douban ID from various fields
    fields_to_extract_douban_id = ["url", "uri", "target_id", "id"]
    douban_id = None
    for field_name in fields_to_extract_douban_id:
        if field_name in item:
            value = item[field_name]
            if value.isdecimal():
                douban_id = value
            else:
                parsed_url = urlparse(value)
                douban_id = [_ for _ in parsed_url.path.split("/") if _][-1]
            break
    if not douban_id:
        raise ValueError(f"Could not extract Douban ID from item: {item}")

    title = item.get("title")
    if not title:
        raise ValueError(f"Could not extract title from item: {item}")

    # Try to extract year
    year = None
    if "year" in item:
        try:
            year = int(item["year"])
        except (ValueError, TypeError):
            pass
    if not year:
        card_subtitle = item.get("card_subtitle") or item.get("subtitle")
        if card_subtitle:
            parts = card_subtitle.split("/")
            year_str = parts[0].strip()
            year_str: str
            if len(year_str) == 4 and year_str.isdecimal():
                year = int(year_str)

    # Get rating
    rating = None
    if item.get("rating") and item["rating"].get("value"):
        try:
            rating = float(item["rating"]["value"])
        except (ValueError, TypeError):
            pass

    return {
        "douban_id": douban_id,
        "douban_title": title,
        "year": year,
        "rating": rating,
        "raw_data": {
            "detail": item,
            "detail_source": source,
        },
    }


def fetch_douban_item_detail(http_session: requests.Session, douban_id: str) -> dict:
    """
    Fetch movie data from Douban Mobile API and return an Item object
    """
    # Construct the API URL with douban_id
    url = DOUBAN_REXXAR_API_URL.format(douban_id)

    # Make request with redirects enabled
    data = get_json(http_session, url, headers=COMMON_HEADERS, allow_redirects=True)

    result = extract_douban_item_detail(data, url)
    if not result:
        return None

    logger.info(
        "Successfully fetched detail from douban rexxar API"
        f" for douban_id={douban_id}: {result['douban_title']}"
    )
    return result
