from collections import defaultdict
import gzip
import json

import pytest
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


def test_explore_type_filter_not_on_website():
    """Test the explore function with a type filter
    that is not present on the website."""
    result = explore("0,10", tags=["脱口秀"], count=COUNT)
    check_explore_result(
        result,
        lambda item: "脱口秀" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_region_filter_not_on_website():
    """Test the explore function with a region filter
    that is not present on the website."""
    result = explore("1,10", tags=["挪威"], count=COUNT)
    check_explore_result(
        result,
        lambda item: "挪威" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_year_filter_not_on_website():
    """Test the explore function with a year filter
    that is not present on the website."""
    result = explore("9,10", tags=["2015"], count=COUNT)
    check_explore_result(
        result, lambda item: item["rating"] >= 9.0 and item["year"] == 2015
    )


@pytest.mark.skip(reason="This test is skipped because it is a only a tool.")
def test_extract_type_region_from_raw_data_file():
    """Test the extraction of type and region from raw data."""
    raw_data_file = "/path/to/file.gz"  # Replace with the actual path to your file

    tags = defaultdict(int)

    with gzip.open(raw_data_file, "rt", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            raw_data = json.loads(line)
            detail = raw_data["detail"]
            in_blacklist = detail.get("in_blacklist", False)
            if in_blacklist:
                continue

            if "subtitle" in detail or "card_subtitle" in detail:
                subtitle = detail.get("subtitle") or detail.get("card_subtitle")
                if subtitle:
                    parts = [part.strip() for part in subtitle.split("/")]
                    if len(parts) > 1:
                        if len(parts[0]) == 4 and parts[0].isdecimal():
                            parts = parts[1:]
                    parts = parts[:2]  # keep only the first two parts
                    for part in parts:
                        for tag in part.split(" "):
                            tag = tag.strip()
                            if tag:
                                tags[tag] += 1
                continue

            for tag in (
                detail.get("types", [])
                + detail.get("regions", [])
                + detail.get("countries", [])
            ):
                if tag:
                    assert isinstance(tag, str)
                    tags[tag] += 1

    print("Tags sorted:")
    for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True):
        if len(tag) == 4 and tag.isdecimal():  # year
            continue
        if tag.isascii():  # skip English names
            continue
        if "·" in tag:  # skip English names
            continue
        print(f"{tag}: {count}")
