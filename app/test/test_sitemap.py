from itertools import islice
import re

from app.info_provider.sitemap import (
    fetch_sitemap_urls_from_sitemap_index,
    fetch_douban_ids_from_sitemap,
)


def test_extract_douban_ids_from_sitemap():
    """Test extracting Douban IDs from a real Douban sitemap."""
    # Use a real sitemap index URL
    sitemap_index_url = "https://www.douban.com/sitemap_index.xml"

    # Get sitemap URLs from the sitemap index
    # Fetch up to 5 sitemap URLs to ensure we get enough IDs
    sitemap_urls = list(fetch_sitemap_urls_from_sitemap_index(sitemap_index_url))
    assert len(sitemap_urls) > 0, "No sitemap URLs found in the index"

    # Collect IDs from multiple sitemaps if needed
    all_ids = []
    target_count = 10

    for sitemap_url in sitemap_urls:
        # Get IDs from the current sitemap
        new_ids = list(
            islice(
                fetch_douban_ids_from_sitemap(sitemap_url),
                target_count - len(all_ids),
            )
        )
        all_ids.extend(new_ids)

        # If we have enough IDs, stop checking more sitemaps
        if len(all_ids) >= target_count:
            break

    # Verify we got some results
    assert len(all_ids) > 0, "No Douban IDs found in any sitemap"

    # Verify that all returned values are numeric Douban IDs
    for douban_id in all_ids:
        assert re.match(r"^\d+$", douban_id), f"ID {douban_id} is not numeric"
