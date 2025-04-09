def check_detail(
    detail: dict, allow_no_rating: bool = False, allow_no_year: bool = False
) -> None:
    assert isinstance(detail, dict)
    assert "in_blacklist" in detail
    assert detail["in_blacklist"] is None or isinstance(detail["in_blacklist"], bool)
    in_blacklist = detail["in_blacklist"]

    assert "douban_id" in detail
    assert "douban_title" in detail

    assert "year" in detail
    if in_blacklist:
        assert detail["year"] is None
    else:
        if allow_no_year and detail["year"] is None:
            pass
        else:
            assert isinstance(detail["year"], int)
            assert 0 < detail["year"] <= 2099
    assert "rating" in detail

    if in_blacklist:
        assert detail["rating"] is None
    else:
        if allow_no_rating and detail["rating"] is None:
            pass
        else:
            assert isinstance(detail["rating"], float)
            assert 0 <= detail["rating"] <= 10

    assert "type" in detail
    assert detail["type"] in ["movie", "tv"]
    assert "raw_data" in detail
    assert "detail" in detail["raw_data"]
    assert isinstance(detail["raw_data"]["detail"], dict)
    assert "detail_source" in detail["raw_data"]
    assert detail["raw_data"]["detail_source"]
