from typing import Dict, Type, List

from app.config import settings
from app.schedule.base_task import BaseTask

# Registry for all registered tasks
_TASK_REGISTRY: Dict[str, Type[BaseTask]] = {}


def register_task(task_class: Type[BaseTask]) -> Type[BaseTask]:
    """Register a task class in the registry"""
    if settings.DISABLE_SCHEDULER:
        return task_class
    try:
        task_instance = task_class()  # Instantiate to verify properties
        task_type = task_instance.task_type
        _TASK_REGISTRY[task_type] = task_class
        print(f"Registered task: {task_type}")  # For debugging
        return task_class
    except Exception as e:
        print(f"Error registering task {task_class.__name__}: {e}")
        raise


def get_task_class(task_type: str) -> Type[BaseTask]:
    """Get a task class by its type"""
    if task_type not in _TASK_REGISTRY:
        raise KeyError(f"Task type '{task_type}' not registered")
    return _TASK_REGISTRY[task_type]


def get_all_task_types() -> List[str]:
    """Get all registered task types"""
    return list(_TASK_REGISTRY.keys())


def create_task_instance(task_type: str) -> BaseTask:
    """Create a new instance of a task by its type"""
    task_class = get_task_class(task_type)
    return task_class()


# Manual registration of tasks
# flake8: noqa: F401
def register_all_tasks():
    """Register all known task classes explicitly"""
    # This requires explicit imports of all task classes
    from app.schedule.add_recent_items_task import AddRecentItemsTask
    from app.schedule.discover_items_by_type_rank_task import (
        DiscoverItemsByTypeRankTask,
    )
    from app.schedule.discover_lists_by_google_task import DiscoverListsByGoogleTask
    from app.schedule.discover_lists_task import DiscoverListsTask
    from app.schedule.discover_tags_by_google_task import DiscoverTagsByGoogleTask
    from app.schedule.refresh_task import RefreshTask
    from app.schedule.backup_task import BackupTask
    from app.schedule.import_items_task import ImportItemsTask
    from app.schedule.process_queue_task import ProcessQueueTask
    from app.schedule.fetch_sitemap_task import FetchSitemapTask
    from app.schedule.discover_by_explore_task import DiscoverItemsByExploreTask
