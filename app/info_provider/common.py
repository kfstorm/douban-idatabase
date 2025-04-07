from typing import Any, Iterator
from urllib.parse import urlparse
from tqdm import tqdm


COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3",  # noqa: B950
    "Referer": "https://m.douban.com/movie",
}


def read_pages(read_one_page, get_total, get_items, items_per_page) -> Iterator[Any]:
    total = None
    start = 0
    count = items_per_page
    progress_bar = None

    try:
        while total is None or start < total:
            page_data = read_one_page(start, count)
            if total is None:
                total = get_total(page_data)
                # Initialize progress bar after we know the total
                progress_bar = tqdm(total=total)

            for item in get_items(page_data):
                yield item
            if progress_bar:
                progress_bar.update(min(count, total - start))

            # Due to the logic of douban, the count of returned items
            # may be less than the specified count per page.
            # Maybe some items are deleted, hidden, or not available.
            # So we still add the specified count to start.
            start += count
            if start >= total:
                break
    finally:
        if progress_bar:
            progress_bar.close()


def extract_douban_item_detail(item: dict, source: str) -> dict:
    """
    Extract relevant fields from a Douban item detail response
    """
    # Handle missing type field in some APIs (like type_rank)
    if "type" not in item:
        # For movie chart APIs, assume it's a movie
        if "chart/top_list" in source:
            item_type = "movie"  # Default to movie for movie chart APIs
    elif item.get("type") not in ["movie", "tv"]:
        return None
    else:
        item_type = item.get("type")

    # Try to extract Douban ID from various fields
    fields_to_extract_douban_id = ["url", "uri", "target_id", "id"]
    douban_id = None
    for field_name in fields_to_extract_douban_id:
        if field_name in item:
            value = item[field_name]
            if value.isdecimal():
                douban_id = value
            else:
                parsed_url = urlparse(value)
                douban_id = [_ for _ in parsed_url.path.split("/") if _][-1]
            break
    if not douban_id:
        raise ValueError(f"Could not extract Douban ID from item: {item}")

    title = item.get("title")
    if not title:
        raise ValueError(f"Could not extract title from item: {item}")

    # Try to extract year
    year = None
    if "year" in item:
        try:
            year = int(item["year"])
        except (ValueError, TypeError):
            pass

    # Try to extract year from release_date field (used in type_rank API)
    if not year and "release_date" in item:
        release_date = item["release_date"]
        if release_date:
            # Extract year from date formats like "1994-09-10" or just "1994"
            if len(release_date) >= 4 and release_date[:4].isdigit():
                year = int(release_date[:4])
            elif release_date.isdigit():
                year = int(release_date)

    if not year:
        card_subtitle = item.get("card_subtitle") or item.get("subtitle")
        if card_subtitle:
            parts = card_subtitle.split("/")
            year_str = parts[0].strip()
            year_str: str
            if len(year_str) == 4 and year_str.isdecimal():
                year = int(year_str)

    # Get rating - handle different formats
    rating = None
    # Handle array format ["9.7", "50"] from type_rank API
    if (
        item.get("rating")
        and isinstance(item["rating"], list)
        and len(item["rating"]) > 0
    ):
        try:
            rating = float(item["rating"][0])
        except (ValueError, TypeError):
            pass
    # Handle direct score field from type_rank API
    if not rating and "score" in item:
        try:
            rating = float(item["score"])
        except (ValueError, TypeError):
            pass
    # Handle standard format with rating.value
    if not rating and item.get("rating") and item["rating"].get("value"):
        try:
            rating = float(item["rating"]["value"])
        except (ValueError, TypeError):
            pass

    if "in_blacklist" in item:
        in_blacklist = bool(item["in_blacklist"])
    else:
        in_blacklist = False if year or rating else None

    return {
        "douban_id": douban_id,
        "douban_title": title,
        "year": year,
        "rating": rating,
        "type": item_type,
        "in_blacklist": in_blacklist,
        "raw_data": {
            "detail": item,
            "detail_source": source,
        },
    }
