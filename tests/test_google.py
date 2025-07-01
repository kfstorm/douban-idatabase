from itertools import islice

from app.schedule.add_recent_items_task import AddRecentItemsTask
from app.schedule.discover_lists_by_google_task import DiscoverListsByGoogleTask
from app.schedule.discover_tags_by_google_task import DiscoverTagsByGoogleTask


def test_search_and_extract_douban_ids():
    """Test searching for Douban movie IDs and extracting them"""
    task = AddRecentItemsTask()
    douban_ids = list(islice(task.search(), 1))
    assert len(douban_ids) > 0, "No Douban IDs found in search results"
    # Check that IDs are numeric
    for id in douban_ids:
        assert id.isdecimal(), f"Extracted ID '{id}' is not numeric"


def test_search_and_extract_douban_lists():
    """Test searching for Douban lists and extracting them"""
    task = DiscoverListsByGoogleTask()
    list_ids = list(islice(task.search(), 1))
    assert len(list_ids) > 0, "No Douban list IDs found in search results"
    # Check that IDs are not empty
    for id in list_ids:
        assert id, f"Extracted list ID '{id}' is empty"


def test_search_and_extract_douban_tag_names():
    """Test searching for Douban tag names and extracting them"""
    task = DiscoverTagsByGoogleTask()
    tag_names = list(islice(task.search(), 1))
    assert len(tag_names) > 0, "No Douban tag names found in search results"
    # Check that tag names are not empty
    for tag_name in tag_names:
        assert tag_name, f"Extracted tag '{tag_name}' is empty"
