from datetime import datetime
import logging
import time
import pytz

logger = logging.getLogger(__name__)


def parse_douban_time(time_str: str) -> float:
    """Convert Beijing time string to UTC timestamp."""
    # Parse the time string as a naive datetime
    naive_datetime = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    # Localize the naive datetime to Beijing timezone
    beijing_tz = pytz.timezone("Asia/Shanghai")
    beijing_time = beijing_tz.localize(naive_datetime)
    # Convert to UTC
    utc_time = beijing_time.astimezone(pytz.UTC)
    # Return as timestamp
    return utc_time.timestamp()


def timestamp_to_local_time_str(timestamp: float) -> str:
    """Convert unix timestamp to localized date and time string without offset"""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def now_timestamp() -> float:
    """Get current time as unix timestamp"""
    return time.time()


def get_exception_module(exc: Exception = None) -> str:
    """
    Get the module name for an exception.
    If no exception is provided, returns the caller's module name.
    """
    if exc and hasattr(exc, "__module__"):
        # Return the exception's module
        return exc.__module__.split(".")[-1]
    return ""


def record_exception_metrics(exc: Exception, metrics_counter=None):
    """
    Record exception in metrics if not already recorded.

    Args:
        exc: The exception to record
        metrics_counter: The metrics counter to use,
            defaults to imported exception_counts

    Returns:
        The exception object for potential chaining
    """
    if hasattr(exc, "_metric_recorded") and exc._metric_recorded:
        return exc

    # Import here to avoid circular imports
    if metrics_counter is None:
        from .metrics import exception_counts

        metrics_counter = exception_counts

    # Record the exception with type and module info
    exc_type = exc.__class__.__name__
    module = get_exception_module(exc)
    metrics_counter.labels(type=exc_type, module=module).inc()

    # Mark as recorded and return for potential chaining
    exc._metric_recorded = True
    return exc
