from app.info_provider.imdb import _fetch_imdb_id_from_mobile_desc, fetch_imdb_id


def check_imdb_info(imdb_info: dict):
    """Check the structure of the IMDb info dictionary."""
    assert isinstance(imdb_info, dict)
    assert "imdb_id" in imdb_info
    assert isinstance(imdb_info["imdb_id"], str)
    assert imdb_info["imdb_id"].startswith("tt")
    assert "raw_data" in imdb_info
    assert isinstance(imdb_info["raw_data"], dict)
    assert "imdb_id" in imdb_info["raw_data"]
    assert isinstance(imdb_info["raw_data"]["imdb_id"], str)
    assert imdb_info["raw_data"]["imdb_id"] == imdb_info["imdb_id"]
    assert "imdb_source" in imdb_info["raw_data"]
    assert isinstance(imdb_info["raw_data"]["imdb_source"], str)
    assert len(imdb_info["raw_data"]["imdb_source"]) > 0


def test_fetch_imdb_id():
    """Test fetching IMDb ID from Douban movie page."""
    douban_id = "36445098"
    imdb_info = fetch_imdb_id(douban_id, False)
    check_imdb_info(imdb_info)
    assert imdb_info["imdb_id"] == "tt21800162"


def test_fetch_imdb_id_from_mobile_desc():
    """Test fetching IMDb ID from mobile description page."""
    douban_id = "36445098"
    imdb_info = _fetch_imdb_id_from_mobile_desc(douban_id)
    check_imdb_info(imdb_info)
    assert imdb_info["imdb_id"] == "tt21800162"


def test_fetch_imdb_id_from_desktop_html():
    """Test fetching IMDb ID from desktop HTML page."""
    douban_id = "36445098"
    imdb_info = _fetch_imdb_id_from_mobile_desc(douban_id)
    check_imdb_info(imdb_info)
    assert imdb_info["imdb_id"] == "tt21800162"
