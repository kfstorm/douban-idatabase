import json
import os
from typing import Optional, Union
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


def _parse_bool_env_var(env_key: str, default_value: bool) -> bool:
    """Parse a string value to a boolean."""
    value = os.getenv(env_key)
    if not value:
        return default_value
    value = value.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    elif value in ("false", "0", "no"):
        return False
    raise ValueError(f"Cannot parse '{value}' to a boolean.")


class Settings(BaseSettings):
    SQLALCHEMY_DATABASE_URL: str = os.getenv(
        "SQLALCHEMY_DATABASE_URL", "sqlite:///db.sqlite3"
    )

    # Redis settings
    # Format: redis://user:password@host:port/db
    # Example: redis://localhost:6379/0
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # ZenRows settings
    ZENROWS_API_KEY: str = os.getenv("ZENROWS_API_KEY", "")

    # TMDB API settings
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")

    # Queue processing settings
    QUEUE_PROCESS_TIME_LIMIT_SECONDS: int = int(
        os.getenv("QUEUE_PROCESS_TIME_LIMIT_SECONDS", "360")
    )

    # Number of threads to use for queue processing
    QUEUE_PROCESSOR_THREAD_COUNT: int = int(
        os.getenv("QUEUE_PROCESSOR_THREAD_COUNT", "4")
    )

    RATE_LIMIT_DELAY_SECONDS: float = float(
        os.getenv("RATE_LIMIT_DELAY_SECONDS", "600")
    )

    REQUEST_DELAY_MAX_SECONDS: float = float(
        os.getenv("REQUEST_DELAY_MAX_SECONDS", "3")
    )

    RATE_LIMIT_USE_ZENROWS: bool = _parse_bool_env_var("RATE_LIMIT_USE_ZENROWS", False)

    ITEM_REFRESH_INTERVAL_DEFAULT_DAYS: int = int(
        os.getenv("ITEM_REFRESH_INTERVAL_DEFAULT_DAYS", "30")
    )

    ITEM_REFRESH_INTERVAL_MAX_DAYS: int = int(
        os.getenv("ITEM_REFRESH_INTERVAL_MAX_DAYS", "365")
    )

    LIST_REFRESH_MIN_INTERVAL_DAYS: int = int(
        os.getenv("LIST_REFRESH_MIN_INTERVAL_DAYS", "30")
    )
    LIST_REFRESH_MAX_INTERVAL_DAYS: int = int(
        os.getenv("LIST_REFRESH_MAX_INTERVAL_DAYS", "365")
    )
    TAG_REFRESH_INTERVAL_DAYS: int = int(os.getenv("TAG_REFRESH_INTERVAL_DAYS", "30"))

    IMDB_CSV_PATH: str = os.getenv("IMDB_CSV_PATH", "")

    # Backup settings
    BACKUP_ENABLED: bool = _parse_bool_env_var("BACKUP_ENABLED", True)
    BACKUP_INTERVAL_SECONDS: int = int(
        os.getenv("BACKUP_INTERVAL_SECONDS", "86400")
    )  # 24 hours
    BACKUP_DIRECTORY: str = os.getenv("BACKUP_DIRECTORY", ".")
    BACKUP_KEEP_SECONDS: int = int(
        os.getenv("BACKUP_KEEP_SECONDS", "604800")
    )  # 7 days default

    # Logs settings
    LOGS_DIRECTORY: str = os.getenv("LOGS_DIRECTORY", "logs")

    DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS: int = int(
        os.getenv("DISCOVER_LISTS_BY_GOOGLE_MAX_RESULTS", "1000")
    )

    DISABLE_INDIVIDUAL_ITEM_FETCH: bool = _parse_bool_env_var(
        "DISABLE_INDIVIDUAL_ITEM_FETCH", False
    )

    DISCOVER_LISTS_BY_TAG_MIN_FAVORITES: int = int(
        os.getenv("DISCOVER_LISTS_BY_TAG_MIN_FAVORITES", "10")
    )

    DISABLE_SCHEDULER: bool = _parse_bool_env_var(
        "DISABLE_SCHEDULER", False
    )  # Disable scheduler for testing purposes

    # Anonymous API access settings
    ALLOW_ANONYMOUS_API_ACCESS: bool = _parse_bool_env_var(
        "ALLOW_ANONYMOUS_API_ACCESS", False
    )

    # Global rate limiting settings for anonymous users (IP-based)
    ANONYMOUS_RATE_LIMIT: int = int(
        os.getenv("ANONYMOUS_RATE_LIMIT", "1000")
    )  # requests
    ANONYMOUS_WINDOW_SIZE: int = int(
        os.getenv("ANONYMOUS_WINDOW_SIZE", "3600")
    )  # seconds (1 hour)

    # Metrics settings
    DB_METRICS_MIN_UPDATE_INTERVAL_SECONDS: int = int(
        os.getenv("DB_METRICS_MIN_UPDATE_INTERVAL_SECONDS", "600")
    )

    DOUBAN_COOKIE_DBCL2: str = os.getenv("DOUBAN_COOKIE_DBCL2", "")

    DISABLE_IMDB_DESKTOP_HTML_FETCH: bool = _parse_bool_env_var(
        "DISABLE_IMDB_DESKTOP_HTML_FETCH", True
    )

    # Configuration for rate limit fallbacks
    # Comma-separated list of fallback strategies: "ZENROWS,PROXY" or "PROXY,ZENROWS"
    RATE_LIMIT_FALLBACK_STRATEGIES: str = os.getenv(
        "RATE_LIMIT_FALLBACK_STRATEGIES", "PROXY"
    )

    # Proxy settings (for PROXY fallback strategy)
    # Can be a single proxy dict or a list of proxy dicts for rotation
    # Example: [{"http":"http://proxy1:8080"}, {"http":"http://proxy2:8080"}]
    REQUESTS_PROXIES: Optional[Union[dict, list]] = json.loads(
        os.getenv("REQUESTS_PROXIES", "null")
    )

    # Blacklist settings
    BLACKLIST_THRESHOLD: int = int(os.getenv("BLACKLIST_THRESHOLD", "3"))
    BLACKLIST_DURATION: int = int(os.getenv("BLACKLIST_DURATION", "2592000"))  # 30 days

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
