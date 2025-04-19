import logging
from urllib.parse import quote, urlparse
from typing import Iterator, Tuple

from app.http_utils import get_response


logger = logging.getLogger(__name__)

TAG_LISTS_PAGE_SIZE = 15


def fetch_lists_from_tag(
    tag_name: str, min_favorites: int = None
) -> Iterator[Tuple[str, str]]:
    """
    Get lists from a tag.
    """

    url = f"https://www.douban.com/tag/{quote(tag_name)}/doulist"

    page = 0
    while True:
        # Wrap get_response in a with statement
        with get_response(
            url, params={"start": page * TAG_LISTS_PAGE_SIZE}
        ) as response:
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
