import csv
import logging
import os
import re
from typing import Optional

from app.config import settings
from app.http_utils import get_response
from app.info_provider.common import COMMON_HEADERS
from app.utils import ApplicationShutdownException, record_exception_metrics


logger = logging.getLogger(__name__)


DOUBAN_DESKTOP_HTML_URL = "https://movie.douban.com/subject/{}/"
DOUBAN_MOBILE_DESC_URL = "https://www.douban.com/doubanapp/h5/movie/{}/desc"
IMDB_DESKTOP_HTML_PATTERN = re.compile(r"IMDb:.*?(\btt\d+\b)")
IMDB_MOBILE_DESC_PATTERN = re.compile(r"<td>IMDb</td>\s*<td>(tt\d+)</td>")


def _fetch_imdb_id_from_csv(douban_id: str) -> dict:
    if not settings.IMDB_CSV_PATH:
        return None

    # Split the CSV paths by comma
    csv_paths = [path.strip() for path in settings.IMDB_CSV_PATH.split(",")]

    for csv_path in csv_paths:
        if not os.path.exists(csv_path):
            logger.warning(f"IMDb CSV file not found: {csv_path}")
            continue

        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[0].isdigit() and douban_id == row[0]:
                    imdb_id = row[1]
                    if not imdb_id:
                        imdb_id = None
                    logger.info(
                        f"Found IMDb ID for douban_id={douban_id} in CSV {csv_path}."
                        f" IMDb ID: {imdb_id}"
                    )
                    return {
                        "imdb_id": imdb_id,
                        "raw_data": {
                            "imdb_id": imdb_id,
                            "imdb_source": os.path.basename(csv_path),
                        },
                    }

    return None


def _fetch_imdb_id_from_mobile_desc(douban_id: str) -> dict:
    """
    Fetch IMDb ID from Douban movie mobile description page
    """
    return _fetch_imdb_id_with_html_regex(
        douban_id,
        "mobile",
        DOUBAN_MOBILE_DESC_URL,
        IMDB_MOBILE_DESC_PATTERN,
    )


def _fetch_imdb_id_from_desktop_html(douban_id: str) -> dict:
    """
    Fetch IMDb ID from Douban movie desktop HTML page
    """
    return _fetch_imdb_id_with_html_regex(
        douban_id,
        "desktop",
        DOUBAN_DESKTOP_HTML_URL,
        IMDB_DESKTOP_HTML_PATTERN,
    )


def _fetch_imdb_id_with_html_regex(
    douban_id: str,
    html_type: str,
    url_pattern: str,
    imdb_id_pattern: re.Pattern,
) -> dict:
    """
    Fetch IMDb ID for a Douban movie using a custom HTML regex pattern
    """
    url = url_pattern.format(douban_id)
    logger.info(f"Fetching IMDb ID from {html_type} page for douban_id={douban_id}...")

    with get_response(url, headers=COMMON_HEADERS, allow_redirects=True) as response:
        match = imdb_id_pattern.search(response.text)
    if match:
        imdb_id = match.group(1)
    else:
        imdb_id = None
    logger.info(
        f"Found IMDb ID {imdb_id} from {html_type} page for douban_id={douban_id}"
    )
    return {
        "imdb_id": imdb_id,
        "raw_data": {
            "imdb_id": imdb_id,
            "imdb_source": url,
        },
    }


def fetch_imdb_id(douban_id: str, in_blacklist: Optional[bool]) -> dict:
    """
    Fetch IMDb ID for a Douban movie using multiple methods
    """
    first_exception = None

    # Try CSV first
    try:
        result = _fetch_imdb_id_from_csv(douban_id)
        if result:
            return result
    except Exception as e:
        record_exception_metrics(e)
        logger.warning(
            f"Error fetching IMDb ID from CSV for douban_id={douban_id}: {str(e)}"
        )
        first_exception = first_exception or e

    if in_blacklist:
        logging.warning(
            f"Douban ID {douban_id} is in blacklist. Skipping fetching IMDB ID."
        )
        return {
            "imdb_id": None,
            "raw_data": {
                "imdb_id": None,
                "imdb_source": "in_blacklist",
            },
        }

    # Try mobile description page scraping
    try:
        result = _fetch_imdb_id_from_mobile_desc(douban_id)
        if result:
            return result
    except ApplicationShutdownException:
        raise
    except Exception as e:
        record_exception_metrics(e)
        logger.warning(
            "Error fetching IMDb ID from mobile description page"
            f" for douban_id={douban_id}: {str(e)}"
        )
        first_exception = first_exception or e

    # Try main desktop page scraping only if not disabled
    # (because desktop page is slower and costs more traffic)
    if not settings.DISABLE_IMDB_DESKTOP_HTML_FETCH:
        try:
            result = _fetch_imdb_id_from_desktop_html(douban_id)
            if result:
                return result
        except ApplicationShutdownException:
            raise
        except Exception as e:
            record_exception_metrics(e)
            logger.warning(
                "Error fetching IMDb ID from desktop page"
                f" for douban_id={douban_id}: {str(e)}"
            )
            first_exception = first_exception or e

    # If we got here, all methods failed. Re-throw the first exception if we have one
    if first_exception:
        logger.error(f"All IMDb ID fetch methods failed for douban_id={douban_id}")
        raise first_exception

    if not result:
        raise Exception(
            f"Failed to fetch IMDb ID for douban_id={douban_id}"
            " using all available methods"
        )
    return result
