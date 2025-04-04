import re
import gzip
from io import BytesIO
from typing import Iterator, List
from lxml import etree
import requests

from app.http_utils import get_response


def _process_sitemap(
    http_session: requests.Session, sitemap_url: str, xpath_query: str
) -> List[str]:
    """
    Process a sitemap and extract values using the provided XPath query.

    Args:
        http_session: HTTP session to use for requests
        sitemap_url: URL of the sitemap
        xpath_query: XPath query to extract values

    Returns:
        List of extracted values
    """
    with get_response(http_session, sitemap_url) as response:
        # Check if the content is gzipped
        content = response.content
        if response.headers.get(
            "Content-Type"
        ) == "application/x-gzip" or sitemap_url.endswith(".gz"):
            content = gzip.GzipFile(fileobj=BytesIO(content)).read()

        # Parse XML
        root = etree.fromstring(content)

        # The namespace used in sitemaps
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Extract values using the provided XPath query
        return root.xpath(xpath_query, namespaces=namespace)


def fetch_sitemap_urls_from_sitemap_index(
    http_session: requests.Session, sitemap_index_url: str
) -> Iterator[str]:
    """
    Fetch URLs from a sitemap index.

    Args:
        http_session: HTTP session to use for requests
        sitemap_index_url: URL of the sitemap index

    Returns:
        Iterator of URLs found in the sitemap index
    """
    urls = _process_sitemap(
        http_session, sitemap_index_url, "//ns:sitemap/ns:loc/text()"
    )
    for url in urls:
        yield url


def fetch_douban_ids_from_sitemap(
    http_session: requests.Session, sitemap_url: str
) -> Iterator[str]:
    """
    Fetch Douban IDs from a sitemap.

    Args:
        http_session: HTTP session to use for requests
        sitemap_url: URL of the sitemap

    Returns:
        Iterator of Douban IDs
    """
    urls = _process_sitemap(http_session, sitemap_url, "//ns:url/ns:loc/text()")

    # Pattern to match Douban IDs in URLs
    pattern = r"movie\.douban\.com/subject/(\d+)"

    # Extract and yield IDs
    for url in urls:
        match = re.search(pattern, url)
        if match:
            douban_id = match.group(1)
            yield douban_id
