import logging
import requests
from typing import Any, Iterator, List
from tqdm import tqdm

from app.http_utils import get_json


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


class BaseApi:
    def __init__(self, http_session: requests.Session, sub_path: str, items_key: str):
        self.http_session = http_session
        self.base_url = f"https://m.douban.com/rexxar/api/v2/{sub_path}"
        self.headers = {"Referer": f"https://m.douban.com/{sub_path}"}
        self.items_key = items_key

    def get_info(self, id: str) -> Any:
        return get_json(
            self.http_session, f"{self.base_url}/{id}", headers=self.headers
        )

    def _read_one_page(self, id: str, start: int, count: int) -> Any:
        return get_json(
            self.http_session,
            f"{self.base_url}/{id}/items?start={start}&count={count}",
            headers=self.headers,
        )

    def get_items(self, id: str) -> List[Any]:
        logger.info(f"Fetching items for {id} ...")
        items = [
            _
            for _ in read_pages(
                read_one_page=lambda start, count: self._read_one_page(
                    id, start, count
                ),
                get_total=lambda page_data: page_data["total"],
                get_items=lambda page_data: page_data[self.items_key],
                items_per_page=50,
            )
        ]
        logger.info(f"Fetched {len(items)} items for {id}.")
        return items


class CollectionApi(BaseApi):
    def __init__(self, http_session: requests.Session):
        super().__init__(http_session, "subject_collection", "subject_collection_items")


class DoulistApi(BaseApi):
    def __init__(self, http_session: requests.Session):
        super().__init__(http_session, "doulist", "items")


# Reference:
# https://github.com/DIYgod/RSSHub/blob/master/lib/v2/douban/other/recommended.js
class ListsApi:
    def __init__(self, http_session: requests.Session):
        self.http_session = http_session
        self.base_url = "https://frodo.douban.com/api/v2"
        self.headers = {
            "User-Agent": "MicroMessenger/",
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html",  # noqa: B950
        }
        self.api_key = "0ac44ae016490db2204ce0a042db2916"

    def _read_one_page(self, start: int, count: int) -> Any:
        return get_json(
            self.http_session,
            f"{self.base_url}/skynet/new_playlists?apikey={self.api_key}&start={start}&count={count}",
            headers=self.headers,
        )

    def iter_lists(self) -> Iterator[Any]:
        for item in read_pages(
            read_one_page=lambda start, count: self._read_one_page(start, count),
            get_total=lambda page_data: page_data["total"],
            get_items=lambda page_data: page_data["data"][0]["items"],
            items_per_page=50,
        ):
            yield item
