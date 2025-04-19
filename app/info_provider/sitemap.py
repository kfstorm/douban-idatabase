import re
import gzip
from io import BytesIO
from typing import Iterator
from lxml import etree

from app.http_utils import get_response


def _process_sitemap(sitemap_url: str, xpath_query: str) -> Iterator[str]:
    """
    Process a sitemap using streaming and extract values using the provided XPath query.

    Args:
        sitemap_url: URL of the sitemap
        xpath_query: XPath query to extract values

    Returns:
        Iterator of extracted values
    """
    with get_response(sitemap_url, stream=True) as response:
        response.raise_for_status()  # Ensure we got a successful response

        # Determine if content is gzipped based on header or URL extension
        is_gzipped = response.headers.get(
            "Content-Type"
        ) == "application/x-gzip" or sitemap_url.endswith(".gz")

        # Create a file-like object for reading, potentially decompressing on the fly
        stream = (
            BytesIO(response.content)
            if not is_gzipped
            else gzip.GzipFile(fileobj=BytesIO(response.content))
        )

        # The namespace used in sitemaps
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Use iterparse for streaming XML parsing
        # We are interested in the text content of elements matching
        # the xpath query's final step
        # Example: //ns:sitemap/ns:loc/text() -> interested in 'loc' elements
        # Example: //ns:url/ns:loc/text() -> interested in 'loc' elements
        tag_match = re.search(r"/ns:(\w+)/text\(\)$", xpath_query)
        if not tag_match:
            raise ValueError("XPath query must end with /ns:<tag>/text()")
        target_tag = f"{{{namespace['ns']}}}{tag_match.group(1)}"

        context = etree.iterparse(stream, events=("end",), tag=target_tag)

        for _, elem in context:
            if elem.text:
                yield elem.text
            # It's safe to clear the element now that we're done with it
            elem.clear()
            # Also eliminate now-empty references from the root node to elem
            while elem.getprevious() is not None:
                del elem.getparent()[0]


def fetch_sitemap_urls_from_sitemap_index(sitemap_index_url: str) -> Iterator[str]:
    """
    Fetch URLs from a sitemap index using streaming.

    Args:
        sitemap_index_url: URL of the sitemap index

    Returns:
        Iterator of URLs found in the sitemap index
    """
    # The XPath query targets the text content of the 'loc' element within 'sitemap'
    yield from _process_sitemap(sitemap_index_url, "//ns:sitemap/ns:loc/text()")


def fetch_douban_ids_from_sitemap(sitemap_url: str) -> Iterator[str]:
    """
    Fetch Douban IDs from a sitemap using streaming.

    Args:
        sitemap_url: URL of the sitemap

    Returns:
        Iterator of Douban IDs
    """
    # The XPath query targets the text content of the 'loc' element within 'url'
    urls_iterator = _process_sitemap(sitemap_url, "//ns:url/ns:loc/text()")

    # Pattern to match Douban IDs in URLs
    pattern = r"movie\.douban\.com/subject/(\d+)"

    # Extract and yield IDs
    for url in urls_iterator:
        match = re.search(pattern, url)
        if match:
            douban_id = match.group(1)
            yield douban_id
