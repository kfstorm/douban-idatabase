import logging
import requests
from sqlalchemy.orm import Session

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
    # (by check if there are enough TV or Movie lists)
    # and then update the tag record accordingly
    if tag_record and tag_record.fetch:
        fetch_check_list_count = 0
    else:
        fetch_check_list_count = 4
    tv_or_movie_list_count = 0
    count = 0
    for list_type, list_id in fetch_lists_from_tag(http_session, tag_name):
        count += 1
        if count <= fetch_check_list_count:
            if _check_is_tv_or_movie_list(http_session, list_type, list_id):
                tv_or_movie_list_count += 1
        else:
            # All checked lists must be TV or Movie lists
            if tv_or_movie_list_count < fetch_check_list_count:
                logger.info(
                    f"Tag {tag_name} has only {tv_or_movie_list_count} "
                    f"TV/Movie lists out of {fetch_check_list_count}"
                    ", mark as no fetch"
                )
                now = now_timestamp()
                if not tag_record:
                    tag_record = Tag(
                        tag_name=tag_name, fetch=False, last_check_time=now
                    )
                    db.add(tag_record)
                else:
                    tag_record.fetch = False
                    tag_record.last_check_time = now
                    db.commit()
                return
            break

    if tag_record.fetch is None:
        logger.info(f"Tag {tag_name} is a TV/Movie tag")
        tag_record.fetch = True
        db.commit()

    count = 0
    # If it's decided to fetch, we fetch lists again
    for list_type, list_id in fetch_lists_from_tag(http_session, tag_name):
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

    # check if top 10 items have at least 5 TV or movie items.
    check_count = 10
    threshold = 5
    count = 0

    for item in list_api.iter_items(list_id):
        detail_info = extract_douban_item_detail(item, f"{list_type}/{list_id}")
        check_count -= 1
        if detail_info:
            count += 1
            if count >= threshold:
                return True
        if check_count == 0:
            break

    return False
