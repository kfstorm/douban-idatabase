from urllib.parse import urlparse
from requests.adapters import HTTPAdapter


def check_detail(detail: dict):
    assert isinstance(detail, dict)
    assert "in_blacklist" in detail
    assert isinstance(detail["in_blacklist"], bool)
    in_blacklist = detail["in_blacklist"]

    assert "douban_id" in detail
    assert "douban_title" in detail

    assert "year" in detail
    if in_blacklist:
        assert detail["year"] is None
    else:
        assert isinstance(detail["year"], int)
        assert 0 < detail["year"] <= 2099
    assert "rating" in detail

    if in_blacklist:
        assert detail["rating"] is None
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


class CompressionCheckAdapter(HTTPAdapter):
    """HTTP adapter that checks for compression in the response."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def build_response(self, req, resp):
        response = super().build_response(req, resp)

        if urlparse(req.url).path.endswith(".gz"):
            return response
        content_encoding = response.headers.get("content-encoding")
        assert content_encoding in [
            "br",
            "zstd",
            "gzip",
            "deflate",
        ], f"Unexpected content encoding: {content_encoding}"
        return response
