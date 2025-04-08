from collections import defaultdict
import logging
import random
import time
import requests
from urllib.parse import urlencode, urlparse
from enum import Enum, auto

from app.config import settings
from app.utils import (
    now_timestamp,
    record_exception_metrics,
    timestamp_to_local_time_str,
)
from app.metrics import rate_limit_hits, http_requests_total, http_request_duration

logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3"
    )
}

_test_check_response_compression = False


class FallbackStrategy(Enum):
    ZENROWS = auto()
    PROXY = auto()


class RateLimitException(Exception):
    """Exception raised when a rate limit is hit."""

    def __init__(self, next_call_time: float):
        self.next_call_time = next_call_time
        message = (
            f"Rate limited. Next call at {timestamp_to_local_time_str(next_call_time)}"
        )
        super().__init__(message)


NO_PERMISSION_DEFAULT_MESSAGE = "No permission to access this resource."


class NoPermissionException(Exception):
    """Exception raised when there is no permission to access a resource."""

    def __init__(self, message: str):
        super().__init__(message)


class Throttler:
    def __init__(self):
        self.next_call_time = defaultdict(lambda: 0.0)
        # List of fallback strategies to try, in order of preference
        self.fallback_strategies = self._get_fallback_strategies()

    def _get_fallback_strategies(self):
        """Get list of fallback strategies from settings, in order of preference."""
        strategies = []
        if hasattr(settings, "RATE_LIMIT_FALLBACK_STRATEGIES"):
            # Setting should be a comma-separated list like "ZENROWS,PROXY"
            for strategy_name in settings.RATE_LIMIT_FALLBACK_STRATEGIES.split(","):
                try:
                    strategy = FallbackStrategy[strategy_name.strip().upper()]
                    strategies.append(strategy)
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown fallback strategy: {strategy_name}")

        # Default fallback to ZENROWS if strategies list is empty and ZENROWS is enabled
        if (
            not strategies
            and settings.RATE_LIMIT_USE_ZENROWS
            and settings.ZENROWS_API_KEY
        ):
            strategies.append(FallbackStrategy.ZENROWS)

        return strategies

    def _check_rate_limit(self, host: str, fallback_strategy: FallbackStrategy):
        if fallback_strategy is not None:
            return
        next_call_time = self.next_call_time[host]
        now = now_timestamp()
        if now < next_call_time:
            raise RateLimitException(next_call_time)
        time.sleep(random.uniform(0, settings.REQUEST_DELAY_MAX_SECONDS))

    def _handle_response(self, response: requests.Response):
        all_responses = response.history + [response]
        host = urlparse(all_responses[0].request.url).netloc

        for resp in all_responses:
            # Example response:
            # {
            #     "msg": "doulist_owner_permission",
            #     "code": 1105,
            #     "request": "GET /v2/doulist/158272741/items",
            #     "localized_message": "这是一个非公开的豆列"
            # }
            if (
                resp.status_code == 403 and "permission" in resp.text
            ):  # access douban directly
                message = NO_PERMISSION_DEFAULT_MESSAGE
                try:
                    json_response = resp.json()
                    if "localized_message" in json_response:
                        message = json_response["localized_message"]
                    elif "msg" in json_response:
                        message = json_response["msg"]
                except ValueError:
                    pass
                raise NoPermissionException(message)
            elif resp.status_code == 422:  # access douban via zenrows
                raise NoPermissionException(NO_PERMISSION_DEFAULT_MESSAGE)

            if (
                resp.status_code == 403
                or (
                    resp.status_code == 302
                    and "sec.douban.com" in resp.headers.get("location", "")
                )
                or (resp.status_code == 400 and "subject_ip_rate_limit" in resp.text)
            ):
                # Rate limited.
                next_call_time = now_timestamp() + settings.RATE_LIMIT_DELAY_SECONDS

                # Record rate limit hit
                rate_limit_hits.labels(host=host).inc()

                raise RateLimitException(next_call_time)

        return response

    def get_next_fallback_strategy(self, host, current_strategy=None):
        """
        Get the next fallback strategy to try based on the current one.
        Returns None if no more strategies are available.
        """
        if not self.fallback_strategies:
            return None

        if current_strategy is None:
            return self.fallback_strategies[0]

        try:
            current_index = self.fallback_strategies.index(current_strategy)
            if current_index + 1 < len(self.fallback_strategies):
                return self.fallback_strategies[current_index + 1]
        except ValueError:
            # If current strategy is not in our list, start from the beginning
            return self.fallback_strategies[0]

        return None


throttler = Throttler()


def get_response_via_zenrows(url: str, **kwargs):
    final_url = url
    original_params = kwargs.pop("params", {})
    if original_params:
        if "?" in url:
            final_url = f"{final_url}&{urlencode(original_params)}"
        else:
            final_url = f"{final_url}?{urlencode(original_params)}"
    new_params = {
        "url": final_url,
        "apikey": settings.ZENROWS_API_KEY,
        "custom_headers": "true",
    }
    kwargs["params"] = new_params
    return get_response(
        "https://api.zenrows.com/v1/",
        fallback_strategy=FallbackStrategy.ZENROWS,
        **kwargs,
    )


def get_response_via_proxy(url: str, **kwargs):
    """Make a request using configured proxies."""
    proxies = settings.REQUESTS_PROXIES

    # Handle legacy single proxy configuration
    if isinstance(proxies, dict):
        selected_proxy = proxies
        proxy_info = "single proxy configuration"
    else:
        # Select a random proxy from the list
        proxy_index = random.randrange(len(proxies))
        selected_proxy = proxies[proxy_index]
        proxy_info = f"proxy #{proxy_index+1}/{len(proxies)}"

    logger.info(f"Using {proxy_info} for request to {url}")
    return get_response(
        url,
        fallback_strategy=FallbackStrategy.PROXY,
        proxies=selected_proxy,
        **kwargs,
    )


def can_use_fallback(strategy: FallbackStrategy, host: str):
    """Check if a specific fallback strategy can be used."""
    if strategy == FallbackStrategy.ZENROWS:
        return (
            settings.RATE_LIMIT_USE_ZENROWS
            and settings.ZENROWS_API_KEY
            and "zenrows" not in host
        )
    elif strategy == FallbackStrategy.PROXY:
        return bool(settings.REQUESTS_PROXIES)
    return False


def get_response(url: str, fallback_strategy=None, **kwargs):
    host = urlparse(url).netloc

    if not fallback_strategy:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                + " AppleWebKit/537.36 (KHTML, like Gecko)"
                + " Chrome/121.0.0.0 Safari/537.3"
            )
        }

        # Merge headers if provided in kwargs
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        kwargs["headers"] = headers

    if settings.DOUBAN_COOKIE_DBCL2 and host.endswith(".douban.com"):
        kwargs["cookies"] = kwargs.get("cookies", {})
        kwargs["cookies"]["dbcl2"] = settings.DOUBAN_COOKIE_DBCL2

    start_time = time.time()

    # Check if this host is already known to be rate limited
    try:
        throttler._check_rate_limit(host, fallback_strategy)
    except RateLimitException as e:
        # If host is rate limited and we're not already using a fallback,
        # try to find a suitable fallback strategy
        if fallback_strategy is None:
            next_strategy = throttler.get_next_fallback_strategy(host)

            if next_strategy and can_use_fallback(next_strategy, host):
                logger.warning(
                    f"The host {host} is rate limited until"
                    f" {timestamp_to_local_time_str(e.next_call_time)}."
                    f" Retry via {next_strategy.name}..."
                )

                if next_strategy == FallbackStrategy.ZENROWS:
                    return get_response_via_zenrows(url, **kwargs)
                elif next_strategy == FallbackStrategy.PROXY:
                    return get_response_via_proxy(url, **kwargs)

        record_exception_metrics(e)
        raise e

    try:
        logger.info("Accessing %s", url)
        response = requests.get(url, timeout=60, **kwargs)

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
            throttler.next_call_time[host] = e.next_call_time

            # Attempt fallback if this is not already a fallback request
            if fallback_strategy is None:
                next_strategy = throttler.get_next_fallback_strategy(host)

                if next_strategy and can_use_fallback(next_strategy, host):
                    response.close()
                    logger.warning(
                        f"The host {host} is now rate limited."
                        f" Retry via {next_strategy.name}..."
                    )

                    if next_strategy == FallbackStrategy.ZENROWS:
                        return get_response_via_zenrows(url, **kwargs)
                    elif next_strategy == FallbackStrategy.PROXY:
                        return get_response_via_proxy(url, **kwargs)

            record_exception_metrics(e)
            raise e

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            record_exception_metrics(e)
            logger.error(f"Failed to fetch {url}: {str(e)}")
            raise e

        if _test_check_response_compression:
            if urlparse(url).path.endswith(".gz"):
                return response
            content_encoding = response.headers.get("content-encoding")
            assert content_encoding in [
                "br",
                "zstd",
                "gzip",
                "deflate",
            ], f"Unexpected content encoding: {content_encoding}"
            return response

        return response
    except requests.exceptions.RequestException as e:
        record_exception_metrics(e)
        if not isinstance(e, requests.HTTPError):
            # Record network-level failures
            http_requests_total.labels(host=host, status_code="error").inc()
            logger.error(f"Request exception for {url}: {str(e)}")
        raise e


def get_json(url, **kwargs):
    with get_response(url, **kwargs) as response:
        return response.json()
