import pytest

import app.http_utils
from app.logging_config import setup_logging


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Set up logging for test sessions with DEBUG level and no file output."""
    logger = setup_logging()
    logger.info("Test session started - logging configured")
    return logger


@pytest.fixture(scope="session", autouse=True)
def compression_check():
    app.http_utils._test_check_response_compression = True
    yield
    app.http_utils._test_check_response_compression = False
