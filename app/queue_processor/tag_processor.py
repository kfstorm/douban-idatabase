import logging
import requests
from itertools import islice
from sqlalchemy.orm import Session

from app.config import settings
from app.http_utils import NoPermissionException
from app.info_provider.detail import (
    extract_douban_item_detail,
)
from app.info_provider.lists import get_list_api_by_list_type
from app.info_provider.tags import fetch_lists_from_tag
from app.models import Tag, Queue, add_placeholder_list
from app.queue_processor.common import (
    allow_update_tag,
)
from app.utils import (
    now_timestamp,
    timestamp_to_local_time_str,
)

logger = logging.getLogger(__name__)


def process_tag(db: Session, http_session: requests.Session, queue_item: Queue) -> None:
    """
    Process a queue item of type 'tag'
    """
    tag_name = queue_item.id
    logger.info(f"Processing tag {tag_name} ...")

    # Check if we've processed this tag before
    tag_record = db.query(Tag).filter_by(tag_name=tag_name).first()
    if not allow_update_tag(tag_record):
        return

    # If the tag has not decided to fetch or not,
    # we need to decide first
    # (by check if there are TV or Movie lists)
    # and then update the tag record accordingly
    if tag_record and tag_record.fetch:
        is_tv_or_movie_tag = True
    else:
        fetch_check_list_count = 10
        is_tv_or_movie_tag = any(
            _check_is_tv_or_movie_list(http_session, list_type, list_id)
            for list_type, list_id in islice(
                fetch_lists_from_tag(http_session, tag_name), fetch_check_list_count
            )
        )

    is_or_not_str = "is" if is_tv_or_movie_tag else "is not"
    if not tag_record:
        logger.info(f"Tag {tag_name} {is_or_not_str} a TV/Movie tag.")
        tag_record = Tag(tag_name=tag_name, fetch=is_tv_or_movie_tag)
        db.add(tag_record)
    elif tag_record.fetch is None:
        logger.info(f"Tag {tag_name} {is_or_not_str} a TV/Movie tag.")
        tag_record.fetch = is_tv_or_movie_tag

    if not is_tv_or_movie_tag:
        now = now_timestamp()
        tag_record.last_check_time = now

    db.commit()

    if not is_tv_or_movie_tag:
        return

    count = 0
    # If it's decided to fetch, we fetch lists again with min favorites requirement
    for list_type, list_id in fetch_lists_from_tag(
        http_session,
        tag_name,
        min_favorites=settings.DISCOVER_LISTS_BY_TAG_MIN_FAVORITES,
    ):
        if add_placeholder_list(db, list_type, list_id):
            count += 1

    now = now_timestamp()
    # Update last_check_time only if we actually processed items
    tag_record.last_check_time = now
    logger.info(
        f"Finished processing tag {tag_name}."
        f" Added {count} placeholder lists."
        f" Updated last_check_time of tag to {timestamp_to_local_time_str(now)}"
    )
    db.commit()


def _check_is_tv_or_movie_list(
    http_session: requests.Session, list_type: str, list_id: str
) -> bool:
    list_api = get_list_api_by_list_type(http_session, list_type)

    # check if top 10 items have at least 1 TV or movie items.
    check_count = 10

    try:
        limited_items = islice(list_api.iter_items(list_id), check_count)
        return any(
            extract_douban_item_detail(item, f"{list_type}/{list_id}")
            for item in limited_items
        )
    except NoPermissionException as e:
        logger.warning(
            f"List {list_type}/{list_id} is private or has no permission to access."
            f" {str(e)}"
        )
        return False
