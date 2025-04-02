from typing import Iterator
from app.info_provider.type_rank import TYPE_RANK_INTERVALS, get_rank_details, get_types
from app.http_utils import new_http_session

http_session = new_http_session()

TEST_TYPE_ID = "11"


def test_get_types():
    types = get_types(http_session)
    assert len(types) == 28
    for type_name, type_id in types:
        assert type_name
        assert type_id
        assert isinstance(type_name, str)
        assert isinstance(type_id, str)
        assert len(type_name) > 0
        assert len(type_id) > 0
    assert TEST_TYPE_ID in [_[1] for _ in types]


def test_get_rank_details():
    type_id = "11"
    interval_id = TYPE_RANK_INTERVALS[0]
    page_size = 10
    rank_details = get_rank_details(http_session, type_id, interval_id, page_size)
    assert rank_details is not None
    assert isinstance(rank_details, Iterator)
    check_count = page_size + 1
    count = 0
    for item in rank_details:
        assert isinstance(item, dict)
        assert "douban_id" in item
        assert "douban_title" in item
        assert "year" in item
        assert isinstance(item["year"], int)
        assert 0 < item["year"] <= 2099
        assert "rating" in item
        assert isinstance(item["rating"], float)
        assert 0 <= item["rating"] <= 10
        count += 1
        if count >= check_count:
            break
    assert count == check_count
