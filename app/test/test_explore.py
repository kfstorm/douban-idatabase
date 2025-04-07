from app.info_provider.explore import explore
from app.test.common import check_detail

COUNT = 20


def check_explore_result(result: dict, item_check_func):
    assert len(result["items"]) > 0
    assert result["total"] > 0
    for item in result["items"]:
        check_detail(item)
        item_check_func(item)


def test_explore_with_score_range():
    """Test the explore function with just a score range and no other filters."""
    result = explore("9,10", count=COUNT)
    check_explore_result(result, lambda item: item["rating"] >= 9.0)


def test_explore_with_year_filter():
    """Test the explore function with a score range and a specific year filter."""
    result = explore("9,10", tags=["2023"], count=COUNT)
    check_explore_result(
        result, lambda item: item["rating"] >= 9.0 and item["year"] == 2023
    )


def test_explore_with_type_filter():
    """Test the explore function with a score range, year,
    and a specific type filter."""
    result = explore("9,10", tags=["2023", "喜剧"], count=COUNT)
    check_explore_result(
        result,
        lambda item: item["rating"] >= 9.0
        and item["year"] == 2023
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_with_region_filter():
    """Test the explore function with a score range, year, type,
    and a specific region filter."""
    result = explore("9,10", tags=["2023", "喜剧", "意大利"], count=COUNT)
    check_explore_result(
        result,
        lambda item: item["rating"] >= 9.0
        and item["year"] == 2023
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"]
        and "意大利" in item["raw_data"]["detail"]["card_subtitle"],
    )
