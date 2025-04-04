import logging
from abc import ABC, abstractmethod
import requests
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BaseTask(ABC):
    """Abstract base class for all scheduled tasks"""

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Task type identifier"""
        pass

    @property
    @abstractmethod
    def default_interval(self) -> int:
        """Default interval in seconds between task executions"""
        pass

    @abstractmethod
    def execute(self, db: Session, http_session: requests.Session) -> None:
        """
        Implementation of the task execution. Must be implemented by subclasses.

        Args:
            db: Database session
            http_session: HTTP session (always provided by scheduler)
        """
        pass
