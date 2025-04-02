import logging
from urllib.parse import quote, urlparse
import requests
from typing import Any, Iterator, Tuple
from tqdm import tqdm

from app.http_utils import get_response


logger = logging.getLogger(__name__)


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


def fetch_lists_from_tag(
    http_session: requests.Session, tag_name: str, min_favorites: int = None
) -> Iterator[Tuple[str, str]]:
    """
    Get lists from a tag.
    """

    url = f"https://www.douban.com/tag/{quote(tag_name)}/doulist"

    page = 0
    while True:
        response = get_response(http_session, url, params={"start": page * 15})

        # Parse HTML content
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(response.text, "html.parser")
        dl_tags = soup.find_all("dl")

        has_list_in_page = False
        for dl in dl_tags:
            # Find the doulist URL and extract list ID
            a_tag = dl.find("a")
            list_url = a_tag["href"]
            path = urlparse(list_url).path
            if not path.startswith("/doulist/"):
                continue
            list_id = path.split("/")[2]

            has_list_in_page = True
            if min_favorites is not None:
                # Extract favorite count from meta div
                meta_div = dl.find("div", class_="meta")
                if not meta_div:
                    continue

                meta_text = meta_div.get_text(strip=True)
                fav_match = re.search(r"(\d+)人关注", meta_text)
                if not fav_match:
                    continue

                fav_count = int(fav_match.group(1))

                # Only return lists with enough favorites
                if fav_count >= min_favorites:
                    yield ("doulist", list_id)
            else:
                yield ("doulist", list_id)

        if not has_list_in_page:
            break

        # Move to next page
        page += 1
