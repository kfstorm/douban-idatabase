import logging
import sys
import os
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from app.config import settings


class SizeLimitedTimedRotatingFileHandler(ConcurrentTimedRotatingFileHandler):
    """
    A timed rotating file handler that also enforces a maximum file size.
    If the file exceeds maxBytes before the timed rotation, it will be rotated immediately.
    """

    def __init__(self, *args, maxBytes=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        # First check if we should roll over due to time
        time_rollover = super().shouldRollover(record)

        # Then check if we should roll over due to size
        size_rollover = False
        if self.maxBytes > 0:
            if self.stream is None:
                self.stream = self._open()
            if self.stream.tell() + len(self.format(record)) >= self.maxBytes:
                size_rollover = True

        return time_rollover or size_rollover


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
    # Rotate daily at midnight OR when file exceeds 10MB, whichever comes first
    file_handler = SizeLimitedTimedRotatingFileHandler(
        filename=log_file,
        when="midnight",  # Rotate at midnight each day
        interval=1,  # Rotate every day
        backupCount=5,  # Keep 5 days of logs
        maxBytes=10 * 1024 * 1024,  # 10MB size limit per file
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add handlers to root logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
