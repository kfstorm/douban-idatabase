import json

from app.info_provider.common import extract_douban_item_detail
from app.info_provider.detail import DOUBAN_REXXAR_API_URL, fetch_douban_item_detail
from app.test.common import check_detail


def _test_extract_base(json_text: str, source: str, expected_result: dict):
    """Test extracting item details from a JSON string."""
    obj = json.loads(json_text)
    detail = extract_douban_item_detail(obj, source)
    if expected_result:
        check_detail(detail)
        expected_result["raw_data"] = {
            "detail": obj,
            "detail_source": source,
        }
    assert expected_result == detail


def test_extract_from_doulist_movie():
    """Test extracting item details from a doulist. The item is a movie."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/1178297"
    json_text = """
    {
        "comment": "",
        "rating": {
            "count": 167,
            "max": 10,
            "star_count": 3.5,
            "value": 6.7
        },
        "subtitle": "2006 / 美国 / 喜剧 / Stewart Wade / 乔纳森·贝莱 威尔逊·克鲁兹",
        "title": "咖啡约会",
        "url": "https://movie.douban.com/subject/1987675/",
        "target_id": "1987675",
        "uri": "douban://douban.com/movie/1987675",
        "cover_url": "https://qnmob3.doubanio.com/view/photo/m_ratio_poster/public/p2544607025.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2014-12-12 22:54:49",
        "type": "movie",
        "id": "183031984"
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "1987675",
        "douban_title": "咖啡约会",
        "year": 2006,
        "rating": 6.7,
        "type": "movie",
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_doulist_tv():
    """Test extracting item details from a doulist. The item is a TV show."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/1178297"
    json_text = """
    {
        "comment": "",
        "rating": {
            "count": 128,
            "max": 10,
            "star_count": 3.5,
            "value": 6.7
        },
        "subtitle": "2013 / 美国 / 喜剧 同性 / Sebastian La Cause / Jason Cicci Bradford How",
        "title": "他在我身边 第一季",
        "url": "https://movie.douban.com/subject/26101735/",
        "target_id": "26101735",
        "uri": "douban://douban.com/tv/26101735",
        "cover_url": "https://qnmob3.doubanio.com/view/photo/m_ratio_poster/public/p2204465842.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2014-12-08 21:31:22",
        "type": "tv",
        "id": "182396166"
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "26101735",
        "douban_title": "他在我身边 第一季",
        "year": 2013,
        "rating": 6.7,
        "type": "tv",
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_doulist_note():
    """Test extracting item details from a doulist. The item is a note."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/1178297"
    json_text = """
    {
        "comment": "",
        "rating": null,
        "subtitle": "43赞 · 6回复",
        "title": "【臭皮匠字幕组】所制作的GAY支线“下载地址以及在线地址”（更新中）",
        "url": "https://www.douban.com/note/533590935/",
        "target_id": "533590935",
        "uri": "douban://douban.com/note/533590935",
        "cover_url": "https://qnmob3.doubanio.com/view/note/sqs/public/p31143760.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2016-01-07 19:30:49",
        "type": "note",
        "id": "244849241"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_doulist_music():
    """Test extracting item details from a doulist. The item is a music."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/1178297"
    json_text = """
    {
        "comment": "",
        "rating": {
            "count": 1398,
            "max": 10,
            "star_count": 4.5,
            "value": 8.8
        },
        "subtitle": "姜广涛 胡良伟 蔡壮壮 李望松 马正阳 宝木中阳 / 2018",
        "title": "AWM绝地求生",
        "url": "https://music.douban.com/subject/30440649/",
        "target_id": "30440649",
        "uri": "douban://douban.com/music/30440649",
        "cover_url": "https://qnmob3.doubanio.com/view/subject/m/public/s29985273.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2021-10-13 08:23:15",
        "type": "music",
        "id": "1226329026"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_doulist_drama():
    """Test extracting item details from a doulist. The item is a drama."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/1178297"
    json_text = """
    {
        "comment": "",
        "rating": {
            "count": 2334,
            "max": 10,
            "star_count": 4.0,
            "value": 9.0
        },
        "subtitle": "舞剧 / Matthew Bourne",
        "title": "天鹅湖",
        "url": "https://www.douban.com/location/drama/25808729/",
        "target_id": "25808729",
        "uri": "douban://douban.com/drama/25808729",
        "cover_url": "https://qnmob3.doubanio.com/pview/drama_subject_poster/m/public/7e7b3448280f1b9.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2019-12-29 09:12:43",
        "type": "drama",
        "id": "868704088"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_doulist_book():
    """Test extracting item details from a doulist. The item is a book."""
    source = "https://m.douban.com/rexxar/api/v2/doulist/38391562"
    json_text = """
    {
        "comment": "",
        "rating": {
            "count": 4252,
            "max": 10,
            "star_count": 4.5,
            "value": 9.1
        },
        "subtitle": "秦晖 / 2003 / 复旦大学出版社",
        "title": "传统十论",
        "url": "https://book.douban.com/subject/1076378/",
        "target_id": "1076378",
        "uri": "douban://douban.com/book/1076378",
        "cover_url": "https://qnmob3.doubanio.com/view/subject/l/public/s1473584.jpg?imageView2/2/q/80/w/300/h/300/format/jpg",
        "create_time": "2015-03-29 21:51:25",
        "type": "book",
        "id": "200141679"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_type_rank_movie():
    """Test extracting item details from type_rank API response."""
    source = "https://movie.douban.com/j/chart/top_list?type=11&interval_id=100:90"
    json_text = """
    {
        "rating": [
            "9.7",
            "50"
        ],
        "rank": 1,
        "cover_url": "https://img3.doubanio.com/view/photo/s_ratio_poster/public/p480747492.jpg",
        "is_playable": true,
        "id": "1292052",
        "types": [
            "犯罪",
            "剧情"
        ],
        "regions": [
            "美国"
        ],
        "title": "肖申克的救赎",
        "url": "https://movie.douban.com/subject/1292052/",
        "release_date": "1994-09-10",
        "actor_count": 25,
        "vote_count": 3151308,
        "score": "9.7",
        "actors": [
            "蒂姆·罗宾斯",
            "摩根·弗里曼"
        ],
        "is_watched": true
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "1292052",
        "douban_title": "肖申克的救赎",
        "year": 1994,
        "rating": 9.7,
        "type": "movie",
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_subject_collection():
    """Test extracting item details from a subject collection API response."""
    source = "https://m.douban.com/rexxar/api/v2/subject_collection/EC4IX6YEQ/items"
    json_text = """
    {
      "comment": "",
      "rating": {
        "count": 5860,
        "max": 10,
        "star_count": 3.5,
        "value": 7.4
      },
      "controversy_reason": "",
      "rank_value": 20,
      "pic": {
        "large": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p1837839519.jpg",
        "normal": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p1837839519.jpg"
      },
      "rank": 20,
      "uri": "douban://douban.com/movie/4844730",
      "is_show": false,
      "vendor_icons": [],
      "card_subtitle": "2012 / 美国 / 喜剧 动作 / 弗兰克·克拉斯 / 凯文·詹姆斯 萨尔玛·海耶克",
      "id": "4844730",
      "title": "好景在望",
      "has_linewatch": false,
      "is_released": true,
      "interest": null,
      "color_scheme": {
        "is_dark": true,
        "primary_color_light": "726560",
        "_base_color": [
          0.041666666666666664,
          0.15763546798029557,
          0.796078431372549
        ],
        "secondary_color": "f9f6f4",
        "_avg_color": [
          0.03846153846153851,
          0.11206896551724135,
          0.4549019607843137
        ],
        "primary_color_dark": "4c4340"
      },
      "type": "movie",
      "description": "",
      "tags": [],
      "cover_url": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p1837839519.jpg",
      "photos": [
        "https://img1.doubanio.com/view/photo/m/public/p1845835788.jpg",
        "https://img2.doubanio.com/view/photo/m/public/p1845835711.jpg",
        "https://img3.doubanio.com/view/photo/m/public/p1845835643.jpg",
        "https://img3.doubanio.com/view/photo/m/public/p1845830803.jpg"
      ],
      "actions": [],
      "sharing_url": "https://www.douban.com/doubanapp/dispatch/movie/4844730",
      "url": "https://movie.douban.com/subject/4844730/",
      "honor_infos": [],
      "good_rating_stats": 0,
      "subtype": "movie",
      "null_rating_reason": ""
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "4844730",
        "douban_title": "好景在望",
        "year": 2012,
        "rating": 7.4,
        "type": "movie",
    }
    _test_extract_base(json_text, source, expected_result)


def test_fetch_douban_item_detail(http_session):
    """Test fetching item details from Douban API."""
    # Test with a movie
    douban_id = "1292052"
    detail_info = fetch_douban_item_detail(http_session, douban_id)
    check_detail(detail_info)
    expected_result = {
        "douban_id": "1292052",
        "douban_title": "肖申克的救赎",
        "year": 1994,
        "rating": 9.7,
        "type": "movie",
    }
    expected_result["raw_data"] = {
        "detail": detail_info["raw_data"]["detail"],
        "detail_source": DOUBAN_REXXAR_API_URL.format(douban_id),
    }
    assert expected_result == detail_info
