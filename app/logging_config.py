import logging
import sys
import os
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
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

    # Clear existing handlers to avoid duplicate logging
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create common formatter to avoid duplication
    log_format = "%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Console handler - INFO level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler with rotation - INFO level using multiprocessing-safe handler
    file_handler = ConcurrentTimedRotatingFileHandler(
        filename=log_file,
        when="midnight",  # Rotate at midnight each day
        interval=1,  # Rotate every day
        backupCount=30,  # Keep 30 days of logs
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add handlers to root logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
