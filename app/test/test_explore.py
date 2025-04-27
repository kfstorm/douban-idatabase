from collections import defaultdict
import gettext
import gzip
import json
import logging
from typing import Optional

import pytest
import pycountry
from app.info_provider.explore import PAGE_SIZE, explore
from app.queue_processor.explore_processor import REGION_KEYWORDS, SORTS, TYPES
from app.test.common import check_detail

logger = logging.getLogger(__name__)

DEFAULT_TEST_COUNT = PAGE_SIZE + 1


def check_explore_result(
    result: dict,
    max_count: Optional[int],
    item_check_func,
    allow_no_results: bool = False,
    allow_count_mismatch: bool = False,
    **kwargs,
):
    logger.info(f"Items count: {len(result['items'])}, Total: {result['total']}")

    assert len(result["items"]) <= result["total"]

    if max_count is not None:
        assert len(result["items"]) <= max_count
        if result["total"] >= max_count:
            assert len(result["items"]) == max_count
        elif not allow_count_mismatch:
            assert len(result["items"]) == result["total"]
    elif not allow_count_mismatch:
        assert len(result["items"]) == result["total"]

    if not allow_no_results:
        assert len(result["items"]) > 0
        assert result["total"] > 0
    douban_ids = set()
    for item in result["items"]:
        check_detail(item, **kwargs)
        if item_check_func:
            item_check_func(item)
        assert item["douban_id"] not in douban_ids
        douban_ids.add(item["douban_id"])


def test_explore_with_score_range():
    """Test the explore function with just a score range and no other filters."""
    result = explore("movie", "9,10", max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie" and item["rating"] >= 9.0,
    )


def test_explore_with_year_filter():
    """Test the explore function with a score range and a specific year filter."""
    result = explore("movie", "9,10", tags=["2023"], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and item["rating"] >= 9.0
        and item["year"] == 2023,
    )


def test_explore_with_type_filter():
    """Test the explore function with a score range, year,
    and a specific type filter."""
    result = explore("movie", "9,10", tags=["2023", "喜剧"], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and item["rating"] >= 9.0
        and item["year"] == 2023
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_with_region_filter():
    """Test the explore function with a score range, year, type,
    and a specific region filter."""
    result = explore(
        "movie", "9,10", tags=["2023", "喜剧", "意大利"], max_count=DEFAULT_TEST_COUNT
    )
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and item["rating"] >= 9.0
        and item["year"] == 2023
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"]
        and "意大利" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_type_filter_not_on_website():
    """Test the explore function with a type filter
    that is not present on the website."""
    result = explore("movie", "0,10", tags=["脱口秀"], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and "脱口秀" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_region_filter_not_on_website():
    """Test the explore function with a region filter
    that is not present on the website."""
    result = explore("movie", "1,10", tags=["挪威"], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and "挪威" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_year_filter_not_on_website():
    """Test the explore function with a year filter
    that is not present on the website."""
    result = explore("movie", "9,10", tags=["2015"], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "movie"
        and item["rating"] >= 9.0
        and item["year"] == 2015,
    )


def test_explore_year_range():
    start_year = 1980  # somehow if we use 2010 here, the test will fail
    years = [start_year + i for i in range(10)]
    if start_year >= 2000:
        year_range = f"{start_year}年代"
    else:
        year_range = f"{start_year % 100}年代"
    common_tags = ["喜剧", "中国大陆"]

    def check(result):
        check_explore_result(
            result,
            DEFAULT_TEST_COUNT,
            lambda item: (
                item["type"] == "movie"
                and (item["rating"] is None or item["rating"] <= 1.0)
                and (not item["year"] or min(years) <= item["year"] <= max(years))
                and "喜剧" in item["raw_data"]["detail"]["card_subtitle"]
                and "中国大陆" in item["raw_data"]["detail"]["card_subtitle"]
            ),
            allow_no_results=True,
            allow_no_rating=True,
            allow_no_year=True,
        )

    result_by_year_range = explore("movie", "0,1", tags=common_tags + [year_range])
    check(result_by_year_range)

    results_by_year = [
        explore("movie", "0,1", tags=common_tags + [str(year)]) for year in years
    ]
    for result in results_by_year:
        check(result)

    douban_ids_by_year_range = set(
        item["douban_id"] for item in result_by_year_range["items"]
    )
    douban_ids_by_year = set(
        item["douban_id"] for result in results_by_year for item in result["items"]
    )
    assert douban_ids_by_year_range == douban_ids_by_year


@pytest.mark.skip(reason="This test is skipped because it is a only a tool.")
def test_extract_type_region_from_raw_data_file():
    """Test the extraction of type and region from raw data."""

    # Generated by `sqlite3 /path/to/db.sqlite3 'select raw_data from item' | gzip > /path/to/file.gz`  # noqa: B950
    raw_data_file = "/path/to/file.gz"  # Replace with the actual path to your file

    region_names = set()
    region_list = (
        list(pycountry.countries)
        + list(pycountry.subdivisions)
        + list(pycountry.historic_countries)
    )
    for region in region_list:
        region_names.add(region.name)
        if hasattr(region, "alpha_2") and region.alpha_2:
            region_names.add(region.alpha_2)
        if hasattr(region, "alpha_3") and region.alpha_3:
            region_names.add(region.alpha_3)
        if hasattr(region, "common_name") and region.common_name:
            region_names.add(region.common_name)
        if hasattr(region, "official_name") and region.official_name:
            region_names.add(region.official_name)
    for lang in ["zh_CN", "zh_TW", "es"]:
        translation = gettext.translation(
            "iso3166-1", pycountry.LOCALES_DIR, languages=[lang]
        )
        translation.install()
        for region in region_list:
            region_names.add(translation.gettext(region.name))
            if hasattr(region, "common_name") and region.common_name:
                region_names.add(translation.gettext(region.common_name))
            if hasattr(region, "official_name") and region.official_name:
                region_names.add(translation.gettext(region.official_name))
    region_names = set(name.lower() for name in region_names)

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
                    parts = [
                        [tag.strip() for tag in part.split(" ") if tag.strip()]
                        for part in subtitle.split("/")
                        if part.strip()
                    ]
                    # Typically, subtitle is like year / regions / types / actors(tags)
                    # Try to remove year part
                    if parts:
                        if len(parts[0]) == 1 and parts[0][0].isdecimal():
                            parts = parts[1:]
                    # Try to detect regions part
                    regions_part = []
                    if parts:
                        if any(tag in TYPES for tag in parts[0]):
                            # part 0 is types part
                            regions_part = []
                        else:
                            # part 0 is regions part
                            regions_part = parts[0]
                    for tag in regions_part:
                        tags[tag] += 1
                continue

            for tag in detail.get("regions", []) + detail.get("countries", []):
                if tag:
                    assert isinstance(tag, str)
                    tags[tag] += 1

    print("Tags sorted:")
    for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True):
        # Skip tags with less than 5 occurrences
        if count < 5:
            continue
        if tag in REGION_KEYWORDS:
            suffix = "(known region)"
        elif (
            tag.lower() in region_names
            or "共和国" in tag
            or "地区" in tag
            or "中国" in tag
            or tag.endswith("国")
            or tag.endswith("地区")
            or tag.endswith("共和国")
            or tag.endswith("國")
            or (
                (
                    len(tag) >= 5
                    or any(
                        # tag has chinese characters
                        ord(char) >= 0x4E00 and ord(char) <= 0x9FFF
                        for char in tag
                    )
                )
                and any(region_name in tag.lower() for region_name in region_names)
            )
        ):
            suffix = "(region)"
        else:
            suffix = "(unknown)"

        print(f'"{tag}",  # {count} {suffix}')


def test_explore_tv():
    """Test the explore function with tv type"""
    result = explore(
        "tv", "9,10", tags=["2021", "喜剧", "意大利"], max_count=DEFAULT_TEST_COUNT
    )
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        lambda item: item["type"] == "tv"
        and item["rating"] >= 9.0
        and item["year"] == 2021
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"]
        and "意大利" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_all():
    """Test the explore function to return all items"""
    result = explore("movie", "7,8", tags=["2000", "喜剧"])
    check_explore_result(
        result,
        None,
        lambda item: item["type"] == "movie"
        and item["year"] == 2000
        and 7.0 <= item["rating"] <= 8.0
        and "喜剧" in item["raw_data"]["detail"]["card_subtitle"],
    )


def test_explore_with_sort():
    """Test the explore function with sort parameter"""
    douban_id_sets = []
    for sort in SORTS:
        result = explore("movie", "9,10", sort=sort, max_count=DEFAULT_TEST_COUNT)
        check_explore_result(
            result,
            DEFAULT_TEST_COUNT,
            lambda item: item["type"] == "movie",
        )
        douban_id_sets.append(set(item["douban_id"] for item in result["items"]))
    # Check if the sets of douban_ids are different for different sorts
    for i in range(len(douban_id_sets)):
        for j in range(i + 1, len(douban_id_sets)):
            assert douban_id_sets[i] != douban_id_sets[j]


def test_explore_api_return_invalid_items():
    """Test the explore function to check if it returns invalid items"""
    result = explore("movie", "0,10", tags=["", ""], max_count=DEFAULT_TEST_COUNT)
    check_explore_result(
        result,
        DEFAULT_TEST_COUNT,
        None,
        allow_no_rating=True,
        allow_count_mismatch=True,
    )
