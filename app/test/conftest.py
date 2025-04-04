import pytest

from app.http_utils import new_http_session
from app.logging_config import setup_logging


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Set up logging for test sessions with DEBUG level and no file output."""
    logger = setup_logging()
    logger.info("Test session started - logging configured")
    return logger


@pytest.fixture(scope="session")
def http_session():
    """Fixture to create a new HTTP session for testing."""
    with new_http_session() as session:
        yield session
