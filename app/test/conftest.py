import pytest

from app.http_utils import new_http_session


@pytest.fixture(scope="session")
def http_session():
    """Fixture to create a new HTTP session for testing."""
    with new_http_session() as session:
        yield session
