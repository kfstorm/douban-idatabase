import logging
import random
import time
from urllib.parse import urlparse, parse_qs
import requests
from sqlalchemy.orm import Session
from typing import Any, Iterator, List, Tuple
from .config import settings
from .http import get_json
from .models import Queue


logger = logging.getLogger(__name__)


def read_pages(read_one_page, get_total, get_items, items_per_page) -> Iterator[Any]:
    total = None
    start = 0
    count = items_per_page
    while total is None or start < total:
        page_data = read_one_page(start, count)
        if total is None:
            total = get_total(page_data)
        new_items = get_items(page_data)
        for item in new_items:
            yield item
        start += len(new_items)
        if not new_items:
            break


class BaseApi:
    def __init__(self, http_session: requests.Session, sub_path: str):
        self.http_session = http_session
        self.base_url = f"https://m.douban.com/rexxar/api/v2/{sub_path}"
        self.headers = {"Referer": f"https://m.douban.com/{sub_path}"}

    def get_info(self, id: str) -> Any:
        return get_json(
            self.http_session, f"{self.base_url}/{id}", headers=self.headers
        )

    def _read_one_page(self, id: str, start: int, count: int) -> Any:
        time.sleep(random.uniform(0, settings.DOUBAN_API_REQUEST_DELAY_MAX_SECONDS))
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
        super().__init__(http_session, "subject_collection")


class DoulistApi(BaseApi):
    def __init__(self, http_session: requests.Session):
        super().__init__(http_session, "doulist")


# Reference:
# https://github.com/DIYgod/RSSHub/blob/master/lib/v2/douban/other/recommended.js
class ListsApi:
    def __init__(self, http_session: requests.Session):
        self.http_session = http_session
        self.base_url = "https://frodo.douban.com/api/v2"
        self.headers = {
            "User-Agent": "MicroMessenger/",
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html",
        }
        self.api_key = "0ac44ae016490db2204ce0a042db2916"

    def _read_one_page(self, start: int, count: int) -> Any:
        time.sleep(random.uniform(0, settings.DOUBAN_API_REQUEST_DELAY_MAX_SECONDS))
        return get_json(
            self.http_session,
            f"{self.base_url}/skynet/new_playlists?apikey={self.api_key}&subject_type=movie&start={start}&count={count}",
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


def bootstrap_lists(db: Session, http_session: requests.Session):
    collection_api = CollectionApi(http_session)
    doulist_api = DoulistApi(http_session)
    list_apis = {
        "collection": collection_api,
        "doulist": doulist_api,
    }

    logger.info("Fetching lists...")
    lists = get_lists_to_bootstrap(http_session)
    logger.info(f"Got {len(lists)} lists.")
    for type, id in lists:
        try:
            logger.info(f"Processing list {type} {id} ...")
            list_api = list_apis[type]
            items = list_api.get_items(id)
            for item in items:
                parsed_url = urlparse(item["url"])
                douban_id = [_ for _ in parsed_url.path.split("/") if _][-1]
                db.add(Queue(type="douban_id", id=douban_id))
            db.commit()
        except Exception:
            logger.exception(f"Failed to process list {type} {id}.")

        time.sleep(random.uniform(0, settings.DOUBAN_API_REQUEST_DELAY_MAX_SECONDS))
    logger.info("Processed all lists.")


def get_lists_to_bootstrap(http_session: requests.Session) -> List[Tuple[str, str]]:
    lists_api = ListsApi(http_session)
    lists = set()
    for item in lists_api.iter_lists():
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
        if list_type == "subject_collection":
            lists.add(("collection", list_id))
        elif list_type == "doulist":
            lists.add(("doulist", list_id))
        else:
            logger.warning(f"Unknown list type: {list_type}")
    return lists
