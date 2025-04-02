from typing import Any, Iterator
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
