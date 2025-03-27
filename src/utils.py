from datetime import datetime
import logging
import pytz

logger = logging.getLogger(__name__)


def parse_douban_time(time_str: str) -> datetime:
    """Convert Beijing time string to UTC datetime object."""
    # Parse the time string as a naive datetime
    naive_datetime = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    # Localize the naive datetime to Beijing timezone
    beijing_tz = pytz.timezone("Asia/Shanghai")
    beijing_time = beijing_tz.localize(naive_datetime)
    # Convert to UTC
    utc_time = beijing_time.astimezone(pytz.UTC)
    return utc_time
