from collections import defaultdict
import logging
import random
import time
from typing import Optional, Tuple, List, Any, Dict
import requests
from urllib.parse import urlencode, urlparse
from urllib3.util import Retry
from enum import Enum, auto
from requests.adapters import HTTPAdapter
from requests.exceptions import ProxyError
from http.cookiejar import DefaultCookiePolicy

from app.config import settings
from app.utils import (
    now_timestamp,
    record_exception_metrics,
    timestamp_to_local_time_str,
    ApplicationShutdownException,
)
import app.utils
from app.metrics import (
    http_requests_total,
    http_request_duration,
    proxy_failures_total,
)

logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3"
    )
}

# Max number of *retries* allowed for a specific fallback strategy
# (PROXY/ZENROWS) when a RateLimitException occurs *while using that strategy*.
# The check is `retry_count + 1 <= MAX_RATE_LIMIT_RETRIES`.
# So, a value of 3 means:
# - Initial attempt (retry_count=0)
# - Retry 1 (retry_count=1) if initial fails
# - Retry 2 (retry_count=2) if Retry 1 fails
# - Retry 3 (retry_count=3) if Retry 2 fails
# Total attempts for the strategy = 1 (initial) + MAX_RATE_LIMIT_RETRIES.
MAX_RATE_LIMIT_RETRIES = 3

CHECK_RATE_LIMIT_EXCLUDED_HOSTS = ["api.themoviedb.org"]

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

    def _get_fallback_strategies(self) -> List[FallbackStrategy]:
        """Get list of fallback strategies from settings,
        ensuring each strategy appears at most once."""
        strategies = []
        added_strategies = set()
        if (
            hasattr(settings, "RATE_LIMIT_FALLBACK_STRATEGIES")
            and settings.RATE_LIMIT_FALLBACK_STRATEGIES
        ):
            # Setting should be a comma-separated list like "ZENROWS,PROXY"
            for strategy_name in settings.RATE_LIMIT_FALLBACK_STRATEGIES.split(","):
                strategy_name_clean = strategy_name.strip().upper()
                try:
                    strategy = FallbackStrategy[strategy_name_clean]
                    if strategy not in added_strategies:
                        strategies.append(strategy)
                        added_strategies.add(strategy)
                    else:
                        # Fail fast if a duplicate strategy name is provided
                        raise ValueError(
                            f"Duplicate fallback strategy '{strategy.name}' found in "
                            "RATE_LIMIT_FALLBACK_STRATEGIES."
                            " Each strategy must be unique."
                        )
                except (KeyError, AttributeError):
                    # Fail fast if an unknown strategy name is provided
                    raise ValueError(
                        f"Unknown or invalid fallback strategy specified in "
                        f"RATE_LIMIT_FALLBACK_STRATEGIES: '{strategy_name_clean}'"
                    )

        # Default fallback to ZENROWS if strategies list is empty and ZENROWS is enabled
        if (
            not strategies
            and settings.RATE_LIMIT_USE_ZENROWS
            and settings.ZENROWS_API_KEY
            and FallbackStrategy.ZENROWS
            not in added_strategies  # Ensure default isn't added if already present
        ):
            strategies.append(FallbackStrategy.ZENROWS)
            added_strategies.add(FallbackStrategy.ZENROWS)

        logger.info(f"Effective fallback strategies: {[s.name for s in strategies]}")
        return strategies

    def _check_rate_limit(self, host: str) -> None:
        """
        Checks if a direct request to the host is allowed based on the last known
        rate limit time for that host. If the host is currently rate-limited,
        raises RateLimitException. Otherwise, introduces a small random delay
        before allowing the request to proceed. This check is skipped for hosts
        in CHECK_RATE_LIMIT_EXCLUDED_HOSTS.
        """
        if host in CHECK_RATE_LIMIT_EXCLUDED_HOSTS:
            return
        next_call_time = self.next_call_time[host]
        # Introduce a small random delay for direct requests to mimic human behavior
        # and potentially avoid hitting rate limits proactively.
        time.sleep(random.uniform(0, settings.REQUEST_DELAY_MAX_SECONDS))
        now = now_timestamp()
        if now < next_call_time:
            raise RateLimitException(next_call_time)

    def _handle_response(self, response: requests.Response) -> requests.Response:
        """
        Inspects the response (and its history in case of redirects) for signs
        of rate limiting or permission errors specific to Douban. Raises
        RateLimitException or NoPermissionException if detected.
        """
        all_responses = response.history + [response]
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

                raise RateLimitException(next_call_time)

        return response

    def get_next_fallback_strategy(
        self, host: str, current_strategy: Optional[FallbackStrategy] = None
    ) -> Optional[FallbackStrategy]:
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


class SessionManager:
    """Manages requests.Session objects for connection pooling."""

    def __init__(self):
        # Default session for regular requests
        self.default_session = self._create_new_session()
        # Sessions for each proxy configuration as an array
        self.proxy_sessions = []

        # Initialize all proxy sessions at startup
        self._initialize_proxy_sessions()

    def _get_retry_config(self) -> Retry:
        """Get retry configuration with fixed values."""
        return Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,  # Let requests handle HTTP errors
            respect_retry_after_header=False,
        )

    def _initialize_proxy_sessions(self) -> None:
        """Create sessions for all configured proxies at startup."""
        # Check if proxies are configured
        if not settings.REQUESTS_PROXIES:
            logger.info("No proxies configured, skipping proxy session initialization")
            return

        proxies = settings.REQUESTS_PROXIES

        # Handle legacy single proxy configuration
        if isinstance(proxies, dict):
            proxies = [proxies]

        # Create a session for each proxy and add to the array
        for i, proxy_config in enumerate(proxies):
            session = self._create_new_session()
            session.proxies.update(proxy_config)
            self.proxy_sessions.append(session)
            logger.info(f"Initialized session for proxy #{i + 1}")

    def _create_new_session(self) -> requests.Session:
        """Create a new session with default settings."""
        session = requests.Session()
        # Set default headers
        session.headers.update(DEFAULT_HEADERS)
        # Prevent cookies from being stored by setting an empty allowed domains list
        session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))

        # Configure retries
        retry_config = self._get_retry_config()
        # Apply retry configuration to both http and https
        session.mount("http://", HTTPAdapter(max_retries=retry_config))
        session.mount("https://", HTTPAdapter(max_retries=retry_config))

        return session

    def get_session(self, proxy_index: Optional[int] = None) -> requests.Session:
        """
        Get a session for the given proxy index.

        Args:
            proxy_index: Optional identifier for the proxy (numeric index)

        Returns:
            A requests.Session object
        """
        if proxy_index is None:
            return self.default_session

        # Check if proxy_index is a valid index
        if isinstance(proxy_index, int) and 0 <= proxy_index < len(self.proxy_sessions):
            return self.proxy_sessions[proxy_index]

        # Fallback to default session if proxy index not valid
        logger.warning(f"Proxy session {proxy_index} not found, using default session")
        return self.default_session


# Initialize the session manager
session_manager = SessionManager()


def _prepare_request_context(
    url: str, proxy_index: Optional[int], **kwargs
) -> Tuple[requests.Session, str, Dict[str, Any]]:
    """Prepare session, cookies, and host for the request."""
    host = urlparse(url).netloc
    session = session_manager.get_session(proxy_index)

    # Handle Douban cookies for this specific request
    cookies = {}
    if settings.DOUBAN_COOKIE_DBCL2 and host.endswith(".douban.com"):
        cookies["dbcl2"] = settings.DOUBAN_COOKIE_DBCL2

    # Merge with any provided cookies
    if "cookies" in kwargs:
        cookies.update(kwargs.pop("cookies"))

    if cookies:
        kwargs["cookies"] = cookies

    return session, host, kwargs


def _execute_request(
    session: requests.Session,
    url: str,
    host: str,
    fallback_strategy: Optional[FallbackStrategy],
    **kwargs,
) -> requests.Response:
    """Executes the HTTP GET request and records basic metrics."""
    start_time = time.time()
    try:
        logger.info(f"Accessing {url} with strategy {fallback_strategy}")
        response = session.get(url, timeout=60, **kwargs)

        # Record response duration
        duration = time.time() - start_time
        http_request_duration.labels(host=host).observe(duration)

        # Record request with status code
        http_requests_total.labels(
            host=host,
            status_code=str(response.status_code),
            strategy=fallback_strategy.name if fallback_strategy else "direct",
        ).inc()
        return response
    except requests.exceptions.RequestException as e:
        # Record all request exceptions for general monitoring
        record_exception_metrics(e)
        # Specifically record network-level failures (non-HTTP errors)
        if not isinstance(e, requests.HTTPError):
            http_requests_total.labels(
                host=host,
                status_code="error",
                strategy=fallback_strategy.name if fallback_strategy else "direct",
            ).inc()
        raise


def _apply_zenrows_params(url: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Modify URL and params for ZenRows proxy."""
    final_url = url
    original_params = kwargs.pop("params", {})
    if original_params:
        query_string = urlencode(original_params)
        final_url = f"{final_url}{'?' if '?' not in url else '&'}{query_string}"

    new_params = {
        "url": final_url,
        "apikey": settings.ZENROWS_API_KEY,
        "custom_headers": "true",
    }
    kwargs["params"] = new_params
    return "https://api.zenrows.com/v1/", kwargs


def can_use_fallback(strategy: FallbackStrategy, host: str) -> bool:
    """Check if a specific fallback strategy can be used."""
    if strategy == FallbackStrategy.ZENROWS:
        return (
            settings.RATE_LIMIT_USE_ZENROWS
            and settings.ZENROWS_API_KEY
            # Avoid infinite loop if zenrows itself is rate limited
            and "zenrows.com" not in host
        )
    elif strategy == FallbackStrategy.PROXY:
        # Check if there are any proxies configured
        return bool(session_manager.proxy_sessions)
    return False


def _handle_fallback_or_raise(
    url: str,
    host: str,
    current_strategy: Optional[FallbackStrategy],
    exception: Exception,
    reason: str,  # e.g., "pre-check rate limit", "post-check rate limit", "proxy error"
    **kwargs,
) -> requests.Response:
    """
    Attempts to switch to the next available fallback strategy. If successful,
    makes a recursive call. If not, records the exception and re-raises it.
    """
    next_strategy = throttler.get_next_fallback_strategy(host, current_strategy)
    if next_strategy and can_use_fallback(next_strategy, host):
        logger.info(
            f"Host {host} encountered {reason}."
            f" Switching to fallback {next_strategy.name}..."
        )
        # Pass original URL and kwargs, reset retry count for new strategy chain
        return _get_response_internal(
            url, current_strategy=next_strategy, retry_count=0, **kwargs
        )
    else:
        # No further fallbacks available or usable
        logger.warning(f"Host {host} encountered {reason}. No usable fallbacks remain.")
        record_exception_metrics(exception)
        raise exception


# Rename original function to indicate internal use
def _get_response_internal(
    url: str,
    current_strategy: Optional[FallbackStrategy] = None,
    proxy_index: Optional[int] = None,
    retry_count: int = 0,  # Tracks the number of retries already performed
    **kwargs,
) -> requests.Response:
    """
    Internal function to handle HTTP GET requests with retries, rate limiting,
    and fallback strategies. This function is recursive.
    """
    if app.utils.shutdown_flag:
        raise ApplicationShutdownException(
            "Application is shutting down. HTTP requests are forbidden."
        )

    request_url = url
    request_kwargs = kwargs.copy()
    request_proxy_index = proxy_index
    strategy_for_logging = current_strategy

    # Prepare ZenRows request if that's the strategy
    if current_strategy == FallbackStrategy.ZENROWS:
        request_url, request_kwargs = _apply_zenrows_params(url, **request_kwargs)
        # ZenRows uses the default session, not a proxy session
        request_proxy_index = None

    # Prepare Proxy request if that's the strategy
    elif current_strategy == FallbackStrategy.PROXY:
        if request_proxy_index is None:  # Select random proxy if not specified
            num_proxies = len(session_manager.proxy_sessions)
            if num_proxies == 0:
                # Fail fast if proxy strategy is chosen but no proxies are configured
                logger.error("Proxy strategy selected but no proxies configured.")
                raise ValueError("No proxies available for PROXY strategy.")
            request_proxy_index = random.randrange(num_proxies)
        proxy_id = f"#{request_proxy_index + 1}"
        logger.info(
            f"Using proxy {proxy_id}/{len(session_manager.proxy_sessions)}"
            f" for request to {url}"
        )

    session, host, prepared_kwargs = _prepare_request_context(
        request_url, request_proxy_index, **request_kwargs
    )

    # Before making a direct request (not using a fallback strategy),
    # check if we know we are rate-limited for this host.
    if current_strategy is None:
        try:
            throttler._check_rate_limit(host)
        except RateLimitException as e:
            # Pre-check failed: Rate limited for direct request.
            # Try fallbacks immediately.
            return _handle_fallback_or_raise(
                url, host, None, e, "pre-check rate limit", **kwargs
            )

    # Execute the request (only reached if pre-check passed or using a fallback)
    try:
        response = _execute_request(
            session, request_url, host, strategy_for_logging, **prepared_kwargs
        )
    except ProxyError as e:
        # Handle proxy-specific errors
        if current_strategy == FallbackStrategy.PROXY:
            proxy_id = f"#{request_proxy_index + 1}"
            proxy_failures_total.labels(proxy_id=proxy_id).inc()
            logger.error(f"Proxy error with {proxy_id}: {str(e)}")
            # Attempt fallback or raise if none available
            return _handle_fallback_or_raise(
                url, host, current_strategy, e, f"proxy error ({proxy_id})", **kwargs
            )
        # If not a proxy error (shouldn't happen here but for safety), re-raise
        raise

    # Handle response status and potential rate limits
    try:
        throttler._handle_response(response)
        response.raise_for_status()  # Check for HTTP errors (4xx, 5xx)
    except RateLimitException as e:
        # Only update the next call time for the host if the rate limit
        # occurred during a direct request. Rate limits via fallbacks
        # might be specific to the proxy/service, not the target host.
        if current_strategy is None:
            throttler.next_call_time[host] = e.next_call_time
        response.close()  # Close the connection before retrying/raising

        # Handle post-request rate limit retry for fallback strategies
        if current_strategy is not None:
            new_retry_count = retry_count + 1
            # Check if the number of retries performed is less than or equal to
            # the max allowed
            if new_retry_count <= MAX_RATE_LIMIT_RETRIES:
                logger.warning(
                    f"Host {host} rate limited (post-check) with strategy "
                    f"{current_strategy.name}. Retrying "
                    f"({new_retry_count}/{MAX_RATE_LIMIT_RETRIES})..."
                )
                # Retry with the same strategy, incremented count
                return _get_response_internal(
                    url,
                    current_strategy=current_strategy,
                    proxy_index=request_proxy_index,  # Keep same proxy if specified
                    retry_count=new_retry_count,  # Pass the count of this retry attempt
                    **kwargs,
                )
            else:
                # Log that the retry limit for this specific strategy was reached
                logger.warning(
                    f"Host {host} rate limited (post-check) with strategy "
                    f"{current_strategy.name}. Retry limit "
                    f"({MAX_RATE_LIMIT_RETRIES} retries) reached after "
                    f"{1 + MAX_RATE_LIMIT_RETRIES} total attempts."
                )
                # Fall through to try the next fallback strategy

        # Attempt fallback or raise if none available/applicable
        return _handle_fallback_or_raise(
            url, host, current_strategy, e, "post-check rate limit", **kwargs
        )
    except requests.HTTPError as e:
        # Record HTTP errors (4xx, 5xx) and re-raise
        record_exception_metrics(e)
        response.close()
        raise
    except NoPermissionException as e:
        # Specific handling for permission errors detected by throttler
        record_exception_metrics(e)
        response.close()
        raise

    # Check response compression if test flag is enabled
    if _test_check_response_compression:
        if urlparse(request_url).path.endswith(".gz"):
            return response
        content_encoding = response.headers.get("content-encoding")
        expected_encodings = ["br", "zstd", "gzip", "deflate"]
        assert content_encoding in expected_encodings, (
            f"URL: {url}, Strategy: {strategy_for_logging}, "
            f"Encoding: {content_encoding}, Expected: {expected_encodings}"
        )

    return response


# Public facing function
def get_response(url: str, **kwargs) -> requests.Response:
    """Makes an HTTP GET request with built-in retries,
    rate limiting, and fallback strategies."""
    # Initial call starts with retry_count=0
    return _get_response_internal(url, **kwargs)


def get_json(url: str, **kwargs) -> Any:
    """Makes a GET request using get_response and returns the JSON response."""
    # Use the public get_response function
    with get_response(url, **kwargs) as response:
        return response.json()
