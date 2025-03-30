from collections import defaultdict
import random
import time
import requests
from urllib.parse import urlencode, urlparse
import logging
from .config import settings
from .utils import now_timestamp, timestamp_to_local_time_str
from .metrics import rate_limit_hits, http_requests_total, http_request_duration

logger = logging.getLogger(__name__)


class RateLimitException(Exception):
    """Exception raised when a rate limit is hit."""

    def __init__(self, next_call_time: float):
        self.next_call_time = next_call_time
        message = (
            f"Rate limited. Next call at {timestamp_to_local_time_str(next_call_time)}"
        )
        super().__init__(message)


class Throttler:
    def __init__(self):
        self.next_call_time = defaultdict(lambda: 0.0)

    def _check_rate_limit(self, url):
        host = urlparse(url).netloc
        next_call_time = self.next_call_time[host]
        now = now_timestamp()
        if now < next_call_time:
            raise RateLimitException(next_call_time)
        time.sleep(random.uniform(0, settings.REQUEST_DELAY_MAX_SECONDS))

    def _handle_response(self, response):
        host = urlparse(response.url).netloc
        if (
            response.status_code == 403
            or response.status_code == 302
            and "sec.douban.com" in response.headers.get("location", "")
            or response.status_code == 400
            and "subject_ip_rate_limit" in response.text
        ):
            # Rate limited.
            next_call_time = now_timestamp() + settings.RATE_LIMIT_DELAY_SECONDS

            # Record rate limit hit
            rate_limit_hits.labels(host=host).inc()

            raise RateLimitException(next_call_time)
        return response


throttler = Throttler()


def _get_extra_http_client_args():
    return {}


def get_response_via_zenrows(http_session: requests.Session, url: str, **kwargs):
    final_url = url
    original_params = kwargs.pop("params", {})
    if original_params:
        if "?" in url:
            final_url = f"{final_url}{url}&{urlencode(original_params)}"
        else:
            final_url = f"{final_url}{url}?{urlencode(original_params)}"
    new_params = {
        "url": final_url,
        "apikey": settings.ZENROWS_API_KEY,
        "custom_headers": "true",
    }
    kwargs["params"] = new_params
    return get_response(http_session, "https://api.zenrows.com/v1/", **kwargs)


def get_response(http_session: requests.Session, url: str, **kwargs):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3"
        )
    }

    # Merge headers if provided in kwargs
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))

    # Get the host for metrics
    host = urlparse(url).netloc
    start_time = time.time()

    try:
        throttler._check_rate_limit(url)
    except RateLimitException as e:
        if settings.RATE_LIMIT_USE_ZENROWS and settings.ZENROWS_API_KEY:
            logger.warning("Rate limited. Trying via ZenRows API...")
            return get_response_via_zenrows(http_session, url, **kwargs)
        else:
            raise e

    try:
        response = http_session.get(url, headers=headers, timeout=60, **kwargs)

        # Record response duration
        duration = time.time() - start_time
        http_request_duration.labels(host=host).observe(duration)

        # Record request with status code
        http_requests_total.labels(
            host=host, status_code=str(response.status_code)
        ).inc()

        try:
            throttler._handle_response(response)
        except RateLimitException as e:
            host = urlparse(response.url).netloc
            if (
                settings.RATE_LIMIT_USE_ZENROWS
                and settings.ZENROWS_API_KEY
                and host != "api.zenrows.com"
            ):
                response.close()
                logger.warning("Rate limited. Trying via ZenRows API...")
                return get_response_via_zenrows(http_session, url, **kwargs)
            else:
                throttler.next_call_time[host] = e.next_call_time
                raise e

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            raise e

        return response
    except requests.exceptions.RequestException as e:
        # Record network-level failures
        http_requests_total.labels(host=host, status_code="error").inc()
        logger.error(f"Request exception for {url}: {str(e)}")
        raise e


def get_json(http_session, url, **kwargs):
    with get_response(http_session, url, **kwargs) as response:
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
