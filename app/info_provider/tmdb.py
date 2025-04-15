import logging
from typing import Optional, Dict, Any

from requests import HTTPError

from app.config import settings
from app.http_utils import get_json

logger = logging.getLogger(__name__)

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_MOVIE_EXTERNAL_IDS_URL = f"{TMDB_API_BASE_URL}/movie/{{tmdb_id}}/external_ids"
TMDB_TV_SERIES_EXTERNAL_IDS_URL = f"{TMDB_API_BASE_URL}/tv/{{tmdb_id}}/external_ids"
TMDB_FIND_URL = f"{TMDB_API_BASE_URL}/find/{{external_id}}"


def _make_tmdb_request(url: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Make a request to the TMDB API.
    """
    if not settings.TMDB_API_KEY:
        raise ValueError("TMDB API key is not configured")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
    }

    return get_json(url, headers=headers, **kwargs)


def get_imdb_id_from_tmdb_id(tmdb_id: str, media_type: str) -> Optional[str]:
    """
    Get IMDB ID from TMDB ID.

    Args:
        tmdb_id: TMDB ID
        media_type: 'movie' or 'tv'

    Returns:
        IMDB ID as a string or None if not found
    """
    if not tmdb_id:
        raise ValueError("tmdb_id cannot be None or empty")
    if not isinstance(tmdb_id, str):
        raise ValueError("tmdb_id must be a string")
    if not media_type:
        raise ValueError("media_type cannot be None or empty")
    if not isinstance(media_type, str):
        raise ValueError("media_type must be a string")

    if media_type == "movie":
        url = TMDB_MOVIE_EXTERNAL_IDS_URL.format(tmdb_id=tmdb_id)
    elif media_type == "tv":
        url = TMDB_TV_SERIES_EXTERNAL_IDS_URL.format(tmdb_id=tmdb_id)
    else:
        raise ValueError("media_type must be 'movie' or 'tv'")

    try:
        data = _make_tmdb_request(url)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None

    if data and "imdb_id" in data and data["imdb_id"]:
        return data["imdb_id"]

    return None


def get_imdb_id_from_tvdb_id(tvdb_id: str) -> Optional[str]:
    """
    Get IMDB ID from TVDB ID using TMDB's find API.

    Args:
        tvdb_id: TVDB ID

    Returns:
        IMDB ID as a string or None if not found
    """
    if not tvdb_id:
        raise ValueError("tvdb_id cannot be None or empty")
    if not isinstance(tvdb_id, str):
        raise ValueError("tvdb_id must be a string")

    url = TMDB_FIND_URL.format(external_id=tvdb_id)
    params = {"external_source": "tvdb_id"}

    data = _make_tmdb_request(url, params=params)

    if not data:
        return None

    # Check movie results first, then TV results
    all_results = []
    if data.get("movie_results"):
        all_results.extend([(item, "movie") for item in data["movie_results"]])
    if data.get("tv_results"):
        all_results.extend([(item, "tv") for item in data["tv_results"]])
    if not all_results:
        return None

    # Sort by popularity to get the most likely match
    all_results.sort(key=lambda x: x[0].get("popularity", 0), reverse=True)
    most_popular = all_results[0]
    item, media_type = most_popular

    # Get TMDB ID from the most popular result
    if not item.get("id"):
        return None
    tmdb_id = str(item.get("id"))
    if tmdb_id:
        # Use the TMDB ID to get the IMDB ID
        return get_imdb_id_from_tmdb_id(tmdb_id, media_type)

    return None
