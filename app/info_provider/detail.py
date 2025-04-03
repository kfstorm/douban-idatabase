import logging
import requests

from app.http_utils import get_json
from app.info_provider.common import COMMON_HEADERS, extract_douban_item_detail

logger = logging.getLogger(__name__)

DOUBAN_REXXAR_API_URL = "https://m.douban.com/rexxar/api/v2/movie/{}"


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
