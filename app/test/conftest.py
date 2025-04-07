import pytest

from app.http_utils import new_http_session
from app.logging_config import setup_logging
from app.test.common import CompressionCheckAdapter


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Set up logging for test sessions with DEBUG level and no file output."""
    logger = setup_logging()
    logger.info("Test session started - logging configured")
    return logger


@pytest.fixture(scope="session")
def http_session():
    """Fixture to create a new HTTP session for testing."""
    http_adapter = CompressionCheckAdapter()
    with new_http_session(http_adapter) as session:
        yield session
