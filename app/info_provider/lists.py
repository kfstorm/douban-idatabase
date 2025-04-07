import logging
from urllib.parse import parse_qs, urlparse
from typing import Any, Iterator

from app.http_utils import get_json
from app.info_provider.common import read_pages
from app.utils import parse_douban_time


logger = logging.getLogger(__name__)


LIST_ITEMS_PAGE_SIZE = 50
LISTS_PAGE_SIZE = 50


def extract_update_time(list_info: dict) -> int:
    """
    Extract the update time from the list info.
    """
    # Look for update time field
    update_time_str = list_info.get("update_time") or list_info.get("updated_at")

    douban_update_time = None
    if update_time_str:
        douban_update_time = parse_douban_time(update_time_str)
    return douban_update_time


class BaseApi:
    def __init__(self, sub_path: str, items_key: str):
        self.base_url = f"https://m.douban.com/rexxar/api/v2/{sub_path}"
        self.headers = {"Referer": f"https://m.douban.com/{sub_path}"}
        self.items_key = items_key

    def get_info(self, id: str) -> Any:
        return get_json(f"{self.base_url}/{id}", headers=self.headers)

    def _read_one_page(self, id: str, start: int, count: int) -> Any:
        return get_json(
            f"{self.base_url}/{id}/items?start={start}&count={count}",
            headers=self.headers,
        )

    def iter_items(self, id: str) -> Iterator[Any]:
        logger.info(f"Fetching items for {id} ...")
        count = 0
        for item in read_pages(
            read_one_page=lambda start, count: self._read_one_page(id, start, count),
            get_total=lambda page_data: page_data["total"],
            get_items=lambda page_data: page_data[self.items_key],
            items_per_page=LIST_ITEMS_PAGE_SIZE,
        ):
            yield item
            count += 1

        logger.info(f"Fetched {count} items for {id}.")


class CollectionApi(BaseApi):
    def __init__(self):
        super().__init__("subject_collection", "subject_collection_items")


class DoulistApi(BaseApi):
    def __init__(self):
        super().__init__("doulist", "items")


# Reference:
# https://github.com/DIYgod/RSSHub/blob/master/lib/v2/douban/other/recommended.js
class ListsApi:
    def __init__(self):
        self.base_url = "https://frodo.douban.com/api/v2"
        self.headers = {
            "User-Agent": "MicroMessenger/",
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html",  # noqa: B950
        }
        self.api_key = "0ac44ae016490db2204ce0a042db2916"

    def _read_one_page(self, start: int, count: int) -> Any:
        return get_json(
            f"{self.base_url}/skynet/new_playlists?apikey={self.api_key}&start={start}&count={count}",
            headers=self.headers,
        )

    def iter_lists(self) -> Iterator[tuple[str, str]]:
        for item in read_pages(
            read_one_page=lambda start, count: self._read_one_page(start, count),
            get_total=lambda page_data: page_data["total"],
            get_items=lambda page_data: page_data["data"][0]["items"],
            items_per_page=LISTS_PAGE_SIZE,
        ):
            parsed_url = urlparse(item["sharing_url"])
            url_parts = [_ for _ in parsed_url.path.split("/") if _][-2:]
            list_type = url_parts[0]
            list_id = url_parts[1]
            if list_type == "doubanapp" and list_id == "dispatch":
                query_params = parse_qs(parsed_url.query)
                uri = query_params.get("uri", [None])[0]
                if uri:
                    url_parts = [_ for _ in uri.split("/") if _][-2:]
                    list_type = url_parts[0]
                list_id = url_parts[1]
            yield (list_type, list_id)


def get_list_api_by_list_type(list_type: str) -> BaseApi:
    if list_type == "subject_collection":
        return CollectionApi()
    elif list_type == "doulist":
        return DoulistApi()
    else:
        raise ValueError(f"Unknown list type {list_type}")
