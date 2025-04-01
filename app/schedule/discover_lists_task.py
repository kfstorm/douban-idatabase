import logging
import requests
from sqlalchemy.orm import Session
from urllib.parse import parse_qs, urlparse

from app.info_provider.lists import ListsApi
from app.models import add_to_queue
from app.utils import now_timestamp


logger = logging.getLogger(__name__)


def discover_lists(db: Session, http_session: requests.Session):
    logger.info("Adding lists to queue...")

    count = 0
    last_print = now_timestamp()
    lists_api = ListsApi(http_session)
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
        if list_type == "subject_collection" or list_type == "doulist":
            # Use common method to add to queue
            add_to_queue(db, list_type, list_id)
        else:
            logger.warning(f"Unknown list type: {list_type}")
        count += 1
        if now_timestamp() - last_print >= 60:
            logger.info(f"Processed {count} lists.")
            last_print = now_timestamp()

    logger.info(f"Finished adding lists to queue. Total: {count}")
