import re
import gzip
from io import BytesIO
from typing import Iterator
import logging

from app.http_utils import get_response

logger = logging.getLogger(__name__)


def _extract_content_by_regex(sitemap_url: str, pattern: str) -> Iterator[str]:
    """
    Fetch content from a URL, handle potential Gzip decompression, and extract
    parts using regex, processing the response stream chunk by chunk.

    Args:
        sitemap_url: URL of the resource.
        pattern: Regular expression pattern with one capturing group.

    Returns:
        Iterator of matched strings.
    """
    chunk_size = 8192
    overlap_size = 512
    compiled_pattern = re.compile(pattern)
    buffer = ""

    with get_response(sitemap_url, stream=True) as response:
        response.raise_for_status()

        # Determine if content is gzipped based on header or URL extension
        content_type = response.headers.get("Content-Type", "").lower()
        is_gzipped = (
            content_type == "application/x-gzip"
            or content_type == "application/gzip"
            or sitemap_url.endswith(".gz")
        )

        # Determine encoding
        encoding = response.encoding if response.encoding else "utf-8"

        # Create an iterator for byte chunks
        byte_iterator = response.iter_content(chunk_size=chunk_size)

        # Wrap the iterator with GzipFile if necessary for decompression
        if is_gzipped:
            # We need a file-like object for GzipFile. We can adapt the iterator.
            # Create a file-like object from the iterator
            class IterStream(BytesIO):
                def __init__(self, iterator):
                    self._iterator = iterator
                    self._buffer = b""

                def read(self, size=-1):
                    while size < 0 or len(self._buffer) < size:
                        try:
                            chunk = next(self._iterator)
                            if not chunk:
                                break
                            self._buffer += chunk
                        except StopIteration:
                            break
                    result = self._buffer[:size]
                    self._buffer = self._buffer[size:]
                    return result

            # Use GzipFile to wrap the streaming response
            gzip_stream = gzip.GzipFile(fileobj=IterStream(byte_iterator))
            # Now read decompressed chunks from gzip_stream
            # Note: GzipFile.read() might not respect exact chunk_size, but reads blocks
            # We adapt by reading in a loop until we have enough data or stream ends
            decompressed_byte_iterator = iter(lambda: gzip_stream.read(chunk_size), b"")
        else:
            # If not gzipped, use the original byte iterator directly
            decompressed_byte_iterator = byte_iterator

        # Process the (potentially decompressed) byte chunks
        for byte_chunk in decompressed_byte_iterator:
            if not byte_chunk:
                continue

            # Decode the byte chunk to string
            chunk_str = byte_chunk.decode(encoding)

            current_data = buffer + chunk_str

            last_match_end = 0
            for match in compiled_pattern.finditer(current_data):
                yield match.group(1)
                last_match_end = match.end()

            buffer = current_data[last_match_end:]
            if len(buffer) > overlap_size * 2:
                buffer = buffer[-overlap_size:]

        # Process remaining buffer
        if buffer:
            for match in compiled_pattern.finditer(buffer):
                yield match.group(1)


def fetch_sitemap_urls_from_sitemap_index(sitemap_index_url: str) -> Iterator[str]:
    """
    Fetch URLs from a sitemap index using regex.

    Args:
        sitemap_index_url: URL of the sitemap index

    Returns:
        Iterator of URLs found in the sitemap index
    """
    # Regex to find content within <loc> tags, non-greedy match
    # Handles potential attributes and whitespace within the loc tag itself
    # Assumes <loc> tags are direct children of <sitemap> conceptually,
    # but doesn't enforce strict hierarchy
    loc_pattern = r"<loc>(.*?)<\/loc>"
    yield from _extract_content_by_regex(sitemap_index_url, loc_pattern)


def fetch_douban_ids_from_sitemap(sitemap_url: str) -> Iterator[str]:
    """
    Fetch Douban IDs from a sitemap using regex.

    Args:
        sitemap_url: URL of the sitemap

    Returns:
        Iterator of Douban IDs
    """
    # First, extract all URLs using the same <loc> pattern
    loc_pattern = r"<loc>(.*?)<\/loc>"
    urls_iterator = _extract_content_by_regex(sitemap_url, loc_pattern)

    # Pattern to match Douban IDs specifically within the extracted URLs
    douban_id_pattern = r"movie\.douban\.com/subject/(\d+)"

    # Extract and yield IDs from the URLs
    for url in urls_iterator:
        match = re.search(douban_id_pattern, url)
        if match:
            douban_id = match.group(1)
            yield douban_id
