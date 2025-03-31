import logging
import sys
from datetime import datetime
import os
from app.config import settings

# Create logs directory if it doesn't exist
logs_dir = os.path.abspath(settings.LOGS_DIRECTORY)
os.makedirs(logs_dir, exist_ok=True)

# Get current date for log filename
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = os.path.join(logs_dir, f"app_{current_date}.log")


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

    # File handler - INFO level
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_format)

    # Add handlers to root logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
