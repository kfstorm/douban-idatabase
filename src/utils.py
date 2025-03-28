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
