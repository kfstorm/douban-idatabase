from datetime import datetime
from app.info_provider.common import extract_douban_item_detail
from app.info_provider.lists import (
    LIST_ITEMS_PAGE_SIZE,
    LISTS_PAGE_SIZE,
    ListsApi,
    extract_update_time,
    get_list_api_by_list_type,
)
from app.test.common import check_detail


def _test_get_list_info(http_session, list_type: str, list_id: str):
    """Test getting info from a list API."""
    list_api = get_list_api_by_list_type(http_session, list_type)
    list_info = list_api.get_info(list_id)
    update_time = extract_update_time(list_info)
    assert update_time is not None
    assert (
        datetime(2000, 1, 1).timestamp()
        <= update_time
        <= datetime(2099, 12, 31).timestamp()
    )


def test_get_subject_collection_info(http_session):
    """Test getting info from a subject collection API."""

    list_type = "subject_collection"
    list_id = "movie_top250"

    _test_get_list_info(http_session, list_type, list_id)


def test_get_doulist_info(http_session):
    """Test getting info from a doulist API."""

    list_type = "doulist"
    list_id = "1178297"

    _test_get_list_info(http_session, list_type, list_id)


def test_get_subject_collection_items(http_session):
    """Test getting items from a subject collection API."""
    list_type = "subject_collection"
    list_id = "movie_top250"
    list_api = get_list_api_by_list_type(http_session, list_type)
    min_count = 250
    count = 0
    for item in list_api.iter_items(list_id):
        detail = extract_douban_item_detail(item, "dummy")
        assert detail is not None
        check_detail(detail)
        count += 1
        if count >= min_count:
            break
    assert count == min_count


def test_get_doulist_items(http_session):
    """Test getting items from a doulist API."""
    list_type = "doulist"
    list_id = "1178297"
    list_api = get_list_api_by_list_type(http_session, list_type)
    min_count = LIST_ITEMS_PAGE_SIZE + 1
    count = 0
    for item in list_api.iter_items(list_id):
        detail = extract_douban_item_detail(item, "dummy")
        assert detail is not None
        count += 1
        if count >= min_count:
            break
    assert count == min_count


def test_lists_api(http_session):
    """Test getting lists from lists API."""
    lists_api = ListsApi(http_session)
    min_count = LISTS_PAGE_SIZE + 1
    count = 0
    for list_type, list_id in lists_api.iter_lists():
        assert list_type in ["subject_collection", "doulist"]
        assert isinstance(list_id, str)
        assert len(list_id) > 0
        count += 1
        if count >= min_count:
            break
    assert count == min_count
