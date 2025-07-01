from typing import Iterator
from app.info_provider.type_rank import TYPE_RANK_INTERVALS, get_rank_details, get_types
from common import check_detail

TEST_TYPE_ID = "11"


def test_get_types():
    types = get_types()
    assert len(types) == 28
    for type_name, type_id in types:
        assert type_name
        assert type_id
        assert isinstance(type_name, str)
        assert isinstance(type_id, str)
        assert len(type_name) > 0
        assert len(type_id) > 0
    assert TEST_TYPE_ID in [_[1] for _ in types]
    # sort and print
    types.sort(key=lambda x: int(x[1]))
    print("Types sorted by ID:")
    for type_name, type_id in types:
        print(f"{type_id}: {type_name}")


def test_get_rank_details():
    type_id = "11"
    interval_id = TYPE_RANK_INTERVALS[0]
    page_size = 10
    details = get_rank_details(type_id, interval_id, page_size)
    assert details is not None
    assert isinstance(details, Iterator)
    check_count = page_size + 1
    count = 0
    for detail in details:
        check_detail(detail)
        count += 1
        if count >= check_count:
            break
    assert count == check_count
