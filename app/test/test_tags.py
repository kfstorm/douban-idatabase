from app.info_provider.tags import TAG_LISTS_PAGE_SIZE, fetch_lists_from_tag


def test_fetch_lists_from_tag(http_session):
    """Test fetching lists from a tag."""
    tag_name = "动作"
    min_count = TAG_LISTS_PAGE_SIZE + 1
    lists = fetch_lists_from_tag(http_session, tag_name)
    count = 0
    for list_type, list_id in lists:
        assert list_type == "doulist"
        assert isinstance(list_id, str)
        count += 1
        if count >= min_count:
            break
    assert count == min_count
