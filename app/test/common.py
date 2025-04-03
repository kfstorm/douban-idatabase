def check_detail(detail: dict):
    assert isinstance(detail, dict)
    assert "douban_id" in detail
    assert "douban_title" in detail
    assert "year" in detail
    assert isinstance(detail["year"], int)
    assert 0 < detail["year"] <= 2099
    assert "rating" in detail
    assert isinstance(detail["rating"], float)
    assert 0 <= detail["rating"] <= 10
    assert "type" in detail
    assert detail["type"] in ["movie", "tv"]
    assert "raw_data" in detail
    assert "detail" in detail["raw_data"]
    assert isinstance(detail["raw_data"]["detail"], dict)
    assert "detail_source" in detail["raw_data"]
    assert detail["raw_data"]["detail_source"]
