import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import os
from app.config import settings

# Create logs directory if it doesn't exist
logs_dir = os.path.abspath(settings.LOGS_DIRECTORY)
os.makedirs(logs_dir, exist_ok=True)

# Base log file path (without date in filename)
log_file = os.path.join(logs_dir, "app.log")


# Configure logging
def setup_logging():
    # Root logger configuration
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler - INFO level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_format)

    # File handler with rotation - INFO level
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",  # Rotate at midnight each day
        interval=1,  # Rotate every day
        backupCount=30,  # Keep 30 days of logs
        encoding="utf-8",
        delay=False,
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_format)
    file_handler.suffix = "%Y-%m-%d"  # Append date to rotated files

    # Add handlers to root logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
