from collections import defaultdict
from datetime import datetime, timedelta
import random
import time
import requests
from urllib.parse import urlparse
import logging
from .config import settings


class RateLimitException(Exception):
    """Exception raised when a rate limit is hit."""

    def __init__(self, next_call_time: datetime):
        self.next_call_time = next_call_time
        message = f"Rate limited. Next call at {next_call_time}"
        super().__init__(message)


class Throttler:
    def __init__(self):
        self.next_call_time = defaultdict(lambda: datetime.min)

    def _check_rate_limit(self, url):
        host = urlparse(url).netloc
        next_call_time = self.next_call_time[host]
        now = datetime.utcnow()
        if now < next_call_time:
            raise RateLimitException(next_call_time)
        time.sleep(random.uniform(0, settings.REQUEST_DELAY_MAX_SECONDS))

    def _handle_response(self, response):
        if (
            response.status_code == 403
            or response.status_code == 302
            and "sec.douban.com" in response.headers.get("location", "")
            or response.status_code == 400
            and "subject_ip_rate_limit" in response.text
        ):
            # Rate limited.
            host = urlparse(response.url).netloc
            next_call_time = datetime.utcnow() + timedelta(
                seconds=settings.RATE_LIMIT_DELAY_SECONDS
            )
            self.next_call_time[host] = next_call_time
            raise RateLimitException(next_call_time)
        return response

    def get_info(self):
        now = datetime.utcnow()
        return {
            key: {
                "is_rate_limited": now < value,
                "next_call_time": str(value) if now < value else None,
            }
            for key, value in self.next_call_time.items()
        }


throttler = Throttler()


def _get_extra_http_client_args():
    return {}


last_throttler_info_print = datetime.utcnow()


def get_response(http_session: requests.Session, url: str, **kwargs):
    global last_throttler_info_print
    now = datetime.utcnow()
    if (now - last_throttler_info_print).total_seconds() > 60:
        last_throttler_info_print = now
        logging.info(f"Throttler info: {throttler.get_info()}")

    throttler._check_rate_limit(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3"
        )
    }

    # Merge headers if provided in kwargs
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))

    response = http_session.get(url, headers=headers, timeout=60, **kwargs)

    throttler._handle_response(response)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        logging.error(f"Failed to fetch {url}: {e}")
        raise e

    return response


def get_json(http_session, url, **kwargs):
    response = get_response(http_session, url, **kwargs)
    return response.json()


def new_http_session():
    http_session = requests.Session()

    http_session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3"
    )

    extra_args = _get_extra_http_client_args()
    if "proxies" in extra_args:
        http_session.proxies = extra_args["proxies"]
    if "cookies" in extra_args:
        for key, value in extra_args["cookies"].items():
            http_session.cookies.set(key, value, domain=".douban.com")

    return http_session
