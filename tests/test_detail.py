import json

from app.info_provider.common import extract_douban_item_detail
from app.info_provider.detail import DOUBAN_REXXAR_API_URL, fetch_douban_item_detail
from common import check_detail


def _test_extract_base(json_text: str, source: str, expected_result: dict, **kwargs):
    """Test extracting item details from a JSON string."""
    obj = json.loads(json_text)
    detail = extract_douban_item_detail(obj, source)
    if expected_result:
        check_detail(detail, **kwargs)
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
        "in_blacklist": False,
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
        "in_blacklist": False,
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
        "in_blacklist": False,
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
        "in_blacklist": False,
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_subject_collection_2():
    """Test extracting item details from a subject collection API response."""
    source = "https://m.douban.com/rexxar/api/v2/subject_collection/movie_real_time_hotest/items"
    json_text = """
    {
        "original_price": "",
        "type_name": "电影",
        "rating": {
            "count": 66613,
            "max": 10,
            "star_count": 4.5,
            "value": 9.1
        },
        "rank_value": 8,
        "pic": {
            "large": "https://img3.doubanio.com/view/photo/m_ratio_poster/public/p2922328832.jpg",
            "normal": "https://img3.doubanio.com/view/photo/s_ratio_poster/public/p2922328832.jpg"
        },
        "is_new": false,
        "actions": [
            "可播放",
            "可购票"
        ],
        "uri": "douban://douban.com/movie/1958667",
        "related_search_terms": [],
        "vendor_icons": [
            "https://img9.doubanio.com/f/frodo/fbc90f355fc45d5d2056e0d88c697f9414b56b44/pics/vendors/tencent.png",
            "https://img9.doubanio.com/f/frodo/6c7b857e6b2255201e73bf83732d95d572f3f9f7/pics/vendors/iqiyi.png"
        ],
        "year": "2001",
        "card_subtitle": "2001 / 日本 / 喜剧 动画 / 原惠一 / 矢岛晶子 楢桥美纪",
        "trend_up": false,
        "id": "1958667",
        "recommended_reason": "",
        "trend_down": false,
        "title": "蜡笔小新：大人王国的反击",
        "trend_equal": true,
        "rank_value_changed": 0,
        "label": "",
        "score": 130700,
        "interest": null,
        "type": "movie",
        "description": "",
        "has_linewatch": true,
        "price": "",
        "rank": 8,
        "date": null,
        "info": "日本 / 喜剧 动画 / 原惠一 / 矢岛晶子 楢桥美纪",
        "url": "https://m.douban.com/movie/subject/1958667/",
        "release_date": "06.28",
        "cover": {
            "url": "https://img3.doubanio.com/view/photo/m_ratio_poster/public/p2922328832.jpg",
            "width": 3624,
            "shape": "rectangle",
            "height": 5098
        },
        "honor_infos": [],
        "subtype": "",
        "reviewer_name": "",
        "null_rating_reason": ""
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "1958667",
        "douban_title": "蜡笔小新：大人王国的反击",
        "year": 2001,
        "rating": 9.1,
        "type": "movie",
        "in_blacklist": False,
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_subject_collection_3():
    """Test extracting item details from a subject collection API response."""
    source = "https://m.douban.com/rexxar/api/v2/subject_collection/movie_real_time_hotest/items"
    json_text = """
    {
        "original_price": "",
        "type_name": "电影",
        "rating": {
        "count": 0,
        "max": 10,
        "star_count": {
            "source": "0.0",
            "parsedValue": 0
        },
        "value": 0
        },
        "rank_value": 9,
        "pic": {
        "large": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p2922813510.jpg",
        "normal": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2922813510.jpg"
        },
        "is_new": false,
        "actions": [],
        "uri": "douban://douban.com/movie/36767956",
        "related_search_terms": [
        {
            "name": "姜文《英雄出少年》定档",
            "uri": "douban://douban.com/search/result?q=%23%E5%A7%9C%E6%96%87%E3%80%8A%E8%8B%B1%E9%9B%84%E5%87%BA%E5%B0%91%E5%B9%B4%E3%80%8B%E5%AE%9A%E6%A1%A3%23"
        },
        {
            "name": "姜文新片《你行！你上！》定档",
            "uri": "douban://douban.com/search/result?q=%23%E5%A7%9C%E6%96%87%E6%96%B0%E7%89%87%E3%80%8A%E4%BD%A0%E8%A1%8C%EF%BC%81%E4%BD%A0%E4%B8%8A%EF%BC%81%E3%80%8B%E5%AE%9A%E6%A1%A3%23"
        }
        ],
        "vendor_icons": [],
        "year": "2025",
        "card_subtitle": "2025 / 中国大陆 / 剧情 喜剧 / 姜文 / 姜文 马丽",
        "trend_up": true,
        "id": "36767956",
        "recommended_reason": "",
        "trend_down": false,
        "title": "你行！你上！",
        "trend_equal": false,
        "rank_value_changed": 1,
        "label": "",
        "score": 119300,
        "interest": null,
        "type": "movie",
        "description": "",
        "has_linewatch": false,
        "price": "",
        "rank": 9,
        "date": null,
        "info": "中国大陆 / 剧情 喜剧 / 姜文 / 姜文 马丽",
        "url": "https://m.douban.com/movie/subject/36767956/",
        "release_date": "07.25",
        "cover": {
        "url": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p2922813510.jpg",
        "width": 3001,
        "shape": "rectangle",
        "height": 4313
        },
        "honor_infos": [],
        "subtype": "",
        "reviewer_name": "",
        "null_rating_reason": "尚未上映"
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "36767956",
        "douban_title": "你行！你上！",
        "year": 2025,
        "rating": None,
        "type": "movie",
        "in_blacklist": False,
    }
    _test_extract_base(json_text, source, expected_result, allow_no_rating=True)


def test_extract_from_rexxar_movie():
    """Test extracting item details from a rexxar API response."""
    source = "https://m.douban.com/rexxar/api/v2/movie/2158666"
    json_text = """
    {
        "rating": {
            "count": 0,
            "max": 10,
            "star_count": 0.0,
            "value": 0
        },
        "controversy_reason": "",
        "title": "未知电影",
        "url": "https://movie.douban.com/subject/2158666/",
        "pic": {
            "large": "https://qnmob3.doubanio.com/f/frodo/753fa1e93c945e533e52dddab73b2b55a1083083/pics/subject/movie_large.jpg?imageView2/2/q/80/w/600/h/3000/format/jpg",
            "normal": "https://qnmob3.doubanio.com/f/frodo/18c01f9a4a16495b333f27b94c1b8ef0bfbd47e0/pics/subject/movie_normal.png?imageView2/2/q/80/w/200/h/300/format/jpg"
        },
        "is_released": false,
        "uri": "douban://douban.com/movie/2158666",
        "cover_url": "https://img2.doubanio.com/f/frodo/753fa1e93c945e533e52dddab73b2b55a1083083/pics/subject/movie_large.jpg",
        "subtype": "",
        "is_show": false,
        "in_blacklist": true,
        "card_subtitle": "",
        "color_scheme": null,
        "type": "movie",
        "id": "2158666",
        "null_rating_reason": "",
        "sharing_url": ""
        }
    """  # noqa: B950
    expected_result = {
        "douban_id": "2158666",
        "douban_title": "未知电影",
        "year": None,
        "rating": None,
        "type": "movie",
        "in_blacklist": True,
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_from_explore():
    """Test extracting item details from an explore API response."""
    source = "dummy"
    json_text = """
    {
        "comment": {
            "comment": "最重要的不過愛與美，哪怕它拒絕著生。",
            "id": "3758839233",
            "user": {
                "kind": "user",
                "name": "白石春子",
                "url": "https://www.douban.com/people/54358731/",
                "uri": "douban://douban.com/user/54358731",
                "avatar": "https://img3.doubanio.com/icon/up54358731-32.jpg",
                "is_club": false,
                "type": "user",
                "id": "54358731",
                "uid": "harukorose"
            }
        },
        "rating": {
            "count": 21499,
            "max": 10,
            "star_count": 4.0,
            "value": 7.8
        },
        "vendor_count": 0,
        "playable_date": null,
        "pic": {
            "large": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p2892253589.jpg",
            "normal": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2892253589.jpg"
        },
        "honor_infos": [
            {
                "kind": "movie",
                "uri": "douban://douban.com/subject_collection/ECCMOLZQA?type=rank&category=movie&rank_type=film_genre",
                "rank": 13,
                "title": "冷门佳作奇幻片榜"
            }
        ],
        "vendor_icons": [],
        "year": "2023",
        "card_subtitle": "2023 / 意大利 法国 瑞士 / 喜剧 爱情 奇幻 冒险 / 阿莉切·罗尔瓦赫尔 / 乔什·奥康纳 卡罗尔·杜阿尔特",
        "id": "35448539",
        "title": "奇美拉",
        "tags": [
            {
                "name": "冷门佳作奇幻片榜",
                "uri": "douban://douban.com/subject_collection/ECCMOLZQA?category=movie&rank_type=film_genre&type=rank"
            },
            {
                "name": "喜欢《无依之地》的也喜欢",
                "uri": "douban://douban.com/movie/recommend_tag?type=like_like&id=30458949"
            },
            {
                "name": "戛纳电影节 金棕榈奖 获奖作品",
                "uri": "douban://douban.com/subject_collection/ECEA6CK3I?category=movie&rank_type=award_movie&type=rank"
            }
        ],
        "interest": null,
        "type": "movie",
        "alg_json": "...",
        "has_linewatch": false,
        "photos": [
            "https://img9.doubanio.com/view/photo/m/public/p2893531406.jpg",
            "https://img9.doubanio.com/view/photo/m/public/p2890652815.jpg",
            "https://img1.doubanio.com/view/photo/m/public/p2873350338.jpg",
            "https://img9.doubanio.com/view/photo/m/public/p2890616034.jpg"
        ],
        "card": "subject",
        "playable_date_info": "",
        "following_rating": null,
        "uri": "douban://douban.com/movie/35448539",
        "episodes_info": "",
        "item_type": "movie"
    }
    """  # noqa: B950
    expected_result = {
        "douban_id": "35448539",
        "douban_title": "奇美拉",
        "year": 2023,
        "rating": 7.8,
        "type": "movie",
        "in_blacklist": False,
    }
    _test_extract_base(json_text, source, expected_result)


def test_extract_invalid_item_doulist_from_explore():
    """Test extracting item details from an explore API response.
    The item is actually a doulist."""
    source = "dummy"
    json_text = """
    {
        "subtitle": "豆瓣片单",
        "is_follow": false,
        "owner": {
            "kind": "user",
            "name": "Clyde",
            "url": "https://www.douban.com/people/2140785/",
            "uri": "douban://douban.com/user/2140785",
            "avatar": "https://img3.doubanio.com/icon/up2140785-3.jpg",
            "is_club": false,
            "type": "user",
            "id": "2140785",
            "uid": "chenhuayang"
        },
        "id": "2604791",
        "category": "movie",
        "title": "不妨一看的外国纪录片",
        "is_subject_selection": false,
        "followers_count": 3209,
        "tile_cover": true,
        "color_scheme": {
            "is_dark": true,
            "primary_color_light": "999ca5",
            "secondary_color": "f4f6f9",
            "primary_color_dark": "76787f"
        },
        "type": "playlist",
        "alg_json": "...",
        "tags": [],
        "syncing_note": null,
        "use_image_cover": true,
        "cover_url": "https://img9.doubanio.com/dae/screenshot/image/v2/html/cos_1b2f1a93d60ced01/profile/subjects_cover",
        "bg_image": "https://img9.doubanio.com/view/photo/photo/public/p2543787426.jpg",
        "doulist_type": "",
        "card": "doulist",
        "items_count": 264,
        "sharing_url": "https://www.douban.com/doulist/2604791/",
        "url": "https://www.douban.com/doulist/2604791/",
        "uri": "douban://douban.com/doulist/2604791",
        "item_type": "movie",
        "list_type": "ugc_doulist"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_extract_invalid_item_ad_from_explore():
    """Test extracting item details from an explore API response.
    The item is actually an ad."""
    source = "dummy"
    json_text = """
    {
        "data": {
            "type": "movie",
            "unit": "dale_movie_ad_second_banner"
        },
        "alg_json": "",
        "type": "ad"
    }
    """  # noqa: B950
    expected_result = None
    _test_extract_base(json_text, source, expected_result)


def test_fetch_douban_item_detail():
    """Test fetching item details from Douban API."""
    # Test with a movie
    douban_id = "1292052"
    detail_info = fetch_douban_item_detail(douban_id)
    check_detail(detail_info)
    expected_result = {
        "douban_id": "1292052",
        "douban_title": "肖申克的救赎",
        "year": 1994,
        "rating": 9.7,
        "type": "movie",
        "in_blacklist": False,
    }
    expected_result["raw_data"] = {
        "detail": detail_info["raw_data"]["detail"],
        "detail_source": DOUBAN_REXXAR_API_URL.format(douban_id),
    }
    assert expected_result == detail_info


def test_fetch_douban_item_detail_in_blacklist():
    """Test fetching item details from Douban API."""
    # Test with a movie in blacklist
    douban_id = "2158666"
    detail_info = fetch_douban_item_detail(douban_id)
    check_detail(detail_info)
    expected_result = {
        "douban_id": "2158666",
        "douban_title": "未知电影",
        "year": None,
        "rating": None,
        "type": "movie",
        "in_blacklist": True,
    }
    expected_result["raw_data"] = {
        "detail": detail_info["raw_data"]["detail"],
        "detail_source": DOUBAN_REXXAR_API_URL.format(douban_id),
    }
    assert expected_result == detail_info
