import os
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
    # ZenRows settings
    ZENROWS_API_KEY: str = os.getenv("ZENROWS_API_KEY", "")

    # API Authentication
    API_KEY: str = os.getenv("API_KEY", "")

    # Queue processing settings
    QUEUE_PROCESS_TIME_LIMIT_SECONDS: int = int(
        os.getenv("QUEUE_PROCESS_TIME_LIMIT_SECONDS", "60")
    )

    RATE_LIMIT_DELAY_SECONDS: float = float(
        os.getenv("RATE_LIMIT_DELAY_SECONDS", "600")
    )

    REQUEST_DELAY_MAX_SECONDS: float = float(
        os.getenv("REQUEST_DELAY_MAX_SECONDS", "3")
    )

    RATE_LIMIT_USE_ZENROWS: bool = _parse_bool_env_var("RATE_LIMIT_USE_ZENROWS", False)

    ITEM_REFRESH_INTERVAL_DAYS_DEFAULT: int = int(
        os.getenv("ITEM_REFRESH_INTERVAL_MINUTES", "30")
    )

    LIST_REFRESH_MIN_INTERVAL_DAYS: int = int(
        os.getenv("LIST_REFRESH_MIN_INTERVAL_DAYS", "30")
    )
    LIST_REFRESH_MAX_INTERVAL_DAYS: int = int(
        os.getenv("LIST_REFRESH_MAX_INTERVAL_DAYS", "365")
    )

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
