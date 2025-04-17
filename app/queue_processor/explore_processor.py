from datetime import datetime
import logging
from sqlalchemy.orm import Session
from typing import Dict

from app.models import Item, Queue, add_placeholder_item, add_to_queue
from app.info_provider.explore import explore
from app.info_provider.imdb import fetch_imdb_id
from app.queue_processor.common import (
    allow_update_item,
    merge_item,
    save_item_to_db,
    wrap_fetch_item,
)

logger = logging.getLogger(__name__)

# This is because the explore API returns a maximum of 500 items
NARROW_THRESHOLD = 500

# Score ranges for exploration. Higher scores come first.
SCORE_RANGES = [f"{i},{i+1}" for i in range(9, -1, -1)]

# Predefined conditions for narrowing down exploration

# Years from 1980 to current year + 5. Later years come first.
YEARS = [str(year) for year in range(datetime.now().year + 5, 1979, -1)]
# Years before 1980. We expect fewer items in these ranges.
YEARS += ["70年代", "60年代", "更早"]

# Based on existing data in database
# Double-checked with https://movie.douban.com/new_subject
TYPES = [
    "剧情",  # 110901
    "喜剧",  # 55030
    "爱情",  # 35192
    "动作",  # 27640
    "惊悚",  # 24146
    "犯罪",  # 22756
    "恐怖",  # 21640
    "动画",  # 20904
    "纪录片",  # 18720
    "短片",  # 16839
    "悬疑",  # 16734
    "冒险",  # 12105
    "科幻",  # 12040
    "奇幻",  # 11009
    "家庭",  # 10032
    "音乐",  # 6871
    "历史",  # 6366
    "战争",  # 6299
    "歌舞",  # 5790
    "传记",  # 5230
    "古装",  # 4566
    "真人秀",  # 3883
    "同性",  # 3851
    "运动",  # 2653
    "西部",  # 2483
    "情色",  # 2438
    "儿童",  # 2086
    "武侠",  # 1889
    "脱口秀",  # 1093
    "黑色电影",  # 642
    "戏曲",  # 508
    "灾难",  # 436
]

# Based on existing data in database
# Generated via test_explore.py#test_extract_type_region_from_raw_data_file
REGION_KEYWORDS = [
    "美国",  # 103299
    "中国大陆",  # 65449
    "日本",  # 43794
    "英国",  # 31288
    "法国",  # 26761
    "中国香港",  # 16203
    "韩国",  # 15671
    "德国",  # 15244
    "加拿大",  # 13766
    "意大利",  # 13213
    "中国台湾",  # 10783
    "西班牙",  # 10103
    "印度",  # 9048
    "澳大利亚",  # 6564
    "俄罗斯",  # 6050
    "巴西",  # 5784
    "墨西哥",  # 5547
    "泰国",  # 5080
    "瑞典",  # 5069
    "阿根廷",  # 4869
    "比利时",  # 4486
    "荷兰",  # 4261
    "丹麦",  # 4120
    "波兰",  # 4068
    "土耳其",  # 3426
    "菲律宾",  # 3232
    "瑞士",  # 3219
    "奥地利",  # 3062
    "苏联",  # 2831
    "芬兰",  # 2741
    "挪威",  # 2685
    "西德",  # 2614
    "葡萄牙",  # 2509
    "匈牙利",  # 2367
    "以色列",  # 2362
    "捷克",  # 2229
    "希腊",  # 2188
    "罗马尼亚",  # 2046
    "爱尔兰",  # 2014
    "新加坡",  # 1965
    "伊朗",  # 1904
    "捷克斯洛伐克",  # 1805
    "印度尼西亚",  # 1497
    "南斯拉夫",  # 1461
    "越南",  # 1457
    "乌克兰",  # 1454
    "智利",  # 1370
    "新西兰",  # 1317
    "保加利亚",  # 1276
    "南非",  # 1259
    "马来西亚",  # 1162
    "哥伦比亚",  # 1149
    "冰岛",  # 1014
    "爱沙尼亚",  # 983
    "克罗地亚",  # 968
    "埃及",  # 947
    "古巴",  # 819
    "塞尔维亚",  # 813
    "拉脱维亚",  # 692
    "立陶宛",  # 619
    "黎巴嫩",  # 612
    "尼日利亚",  # 601
    "秘鲁",  # 565
    "Canada",  # 550
    "斯洛文尼亚",  # 529
    "卢森堡",  # 508
    "格鲁吉亚",  # 464
    "斯洛伐克",  # 464
    "乌拉圭",  # 445
    "阿尔巴尼亚",  # 431
    "委内瑞拉",  # 420
    "USA",  # 418
    "卡塔尔",  # 401
    "摩洛哥",  # 362
    "哈萨克斯坦",  # 327
    "巴基斯坦",  # 314
    "巴勒斯坦",  # 279
    "朝鲜",  # 253
    "孟加拉国",  # 251
    "突尼斯",  # 241
    "波黑",  # 223
    "阿尔及利亚",  # 218
    "波多黎各",  # 214
    "多米尼加",  # 214
    "UK",  # 213
    "India",  # 213
    "东德",  # 198
    "中国",  # 191
    "阿联酋",  # 191
    "厄瓜多尔",  # 190
    "白俄罗斯",  # 189
    "亚美尼亚",  # 179
    "尼泊尔",  # 177
    "叙利亚",  # 177
    "沙特阿拉伯",  # 175
    "Australia",  # 174
    "柬埔寨",  # 172
    "中国澳门",  # 169
    "玻利维亚",  # 163
    "斯里兰卡",  # 161
    "塞内加尔",  # 159
    "蒙古",  # 157
    "伊拉克",  # 154
    "缅甸",  # 151
    "Turkey",  # 150
    "哥斯达黎加",  # 149
    "塞浦路斯",  # 146
    "肯尼亚",  # 142
    "阿塞拜疆",  # 138
    "阿富汗",  # 136
    "北马其顿",  # 124
    "约旦",  # 123
    "蘇聯",  # 121
    "科索沃",  # 121
    "印尼",  # 118
    "危地马拉",  # 106
    "Russia",  # 101
    "乌兹别克斯坦",  # 97
    "布基纳法索",  # 93
    "吉尔吉斯斯坦",  # 93
    "前苏联",  # 91
    "巴拉圭",  # 90
    "巴拿马",  # 88
    "黑山",  # 88
    "摩纳哥",  # 87
    "马其顿",  # 84
    "Germany",  # 82
    "Indonesia",  # 82
    "尼加拉瓜",  # 79
    "Netherlands",  # 77
    "加纳",  # 72
    "Poland",  # 70
    "Sweden",  # 69
    "Mexico",  # 69
    "俄国",  # 67
    "埃塞俄比亚",  # 65
    "Austria",  # 65
    "刚果",  # 65
    "马耳他",  # 63
    "喀麦隆",  # 61
    "Greece",  # 60
    "France",  # 58
    "Denmark",  # 57
    "Belgium",  # 57
    "老挝",  # 55
    "Ireland",  # 54
    "Argentina",  # 52
    "Soviet",  # 51
    "科威特",  # 50
    "Portugal",  # 50
    "Singapore",  # 49
    "Union",  # 49
    "Brazil",  # 49
    "波斯尼亚和黑塞哥维那",  # 49
    "孟加拉",  # 48
    "Philippines",  # 48
    "Indian",  # 45
    "马里",  # 43
    "Switzerland",  # 43
    "Hungary",  # 43
    "Norway",  # 41
    "不丹",  # 40
    "New",  # 39
    "俄羅斯",  # 39
    "Finland",  # 39
    "香港",  # 38
    "塞黑",  # 37
    "Republic",  # 37
    "圣马力诺",  # 37
    "津巴布韦",  # 36
    "Czech",  # 36
    "澳洲",  # 35
    "Zealand",  # 34
    "South",  # 34
    "Italy",  # 33
    "摩尔多瓦",  # 33
    "Israel",  # 33
    "Kazakhstan",  # 32
    "West",  # 32
    "Romania",  # 32
    "Ukraine",  # 32
    "塔吉克斯坦",  # 31
    "英國",  # 31
    "Vietnam",  # 31
    "台灣",  # 30
    "Cyprus",  # 30
    "BBC",  # 29
    "Chile",  # 29
    "Czechoslovakia",  # 29
    "Africa",  # 29
    "Spain",  # 28
    "Iran",  # 28
    "Iceland",  # 28
    "Palestine",  # 27
    "多米尼加共和国",  # 27
    "加拿大Canada",  # 27
    "乍得",  # 26
    "尼日尔",  # 25
    "联邦德国",  # 25
    "列支敦士登",  # 24
    "海地",  # 24
    "苏丹",  # 24
    "萨尔瓦多",  # 22
    "索马里",  # 22
    "Lebanon",  # 21
    "Bulgaria",  # 21
    "Senegal",  # 21
    "Peru",  # 21
    "China",  # 20
    "卢旺达",  # 20
    "india",  # 20
    "丹麥",  # 20
    "洪都拉斯",  # 20
    "Lithuania",  # 19
    "Cambodia",  # 19
    "安哥拉",  # 19
    "Cuba",  # 19
    "Venezuela",  # 19
    "Egypt",  # 19
    "Taiwan",  # 19
    "莫桑比克",  # 19
    "原西德",  # 18
    "Belarus",  # 18
    "Colombia",  # 18
    "Croatia",  # 18
    "佛得角",  # 17
    "US",  # 17
    "argentina",  # 17
    "Kenya",  # 16
    "牙买加",  # 16
    "科特迪瓦",  # 16
    "毛里塔尼亚",  # 16
    "Japan",  # 16
    "坦桑尼亚",  # 16
    "法罗群岛",  # 16
    "乌干达",  # 16
    "格陵兰",  # 15
    "Guatemala",  # 15
    "几内亚比绍",  # 15
    "Malaysia",  # 15
    "uk",  # 15
    "Armenia",  # 14
    "United",  # 14
    "brasil",  # 14
    "Syria",  # 14
    "Philippine",  # 14
    "Jamaica",  # 13
    "Arab",  # 13
    "巴林",  # 13
    "也门",  # 13
    "德國",  # 13
    "Bolivia",  # 13
    "Russian",  # 13
    "台灣Taiwan",  # 13
    "Serbia",  # 13
    "Myanmar",  # 13
    "Pakistan",  # 13
    "刚果（金）",  # 13
    "利比亚",  # 12
    "博茨瓦纳",  # 12
    "美國",  # 12
    "巴哈马",  # 12
    "Emirates",  # 12
    "usa",  # 12
    "Haiti",  # 12
    "canada",  # 12
    "比利時",  # 12
    "纳米比亚",  # 12
    "阿拉伯联合酋长国",  # 12
    "poland",  # 12
    "阿鲁巴",  # 11
    "加蓬",  # 11
    "赞比亚",  # 11
    "The",  # 11
    "Korea",  # 11
    "Burkina",  # 11
    "Faso",  # 11
    "捷克共和国",  # 11
    "Slovakia",  # 11
    "Netherland",  # 11
    "Uruguay",  # 11
    "马达加斯加",  # 11
    "Nepal",  # 11
    "Qatar",  # 11
    "苏里南",  # 11
    "菲律宾Philippine",  # 11
    "Estonia",  # 11
    "Cameroon",  # 10
    "贝宁",  # 10
    "安道尔",  # 10
    "and",  # 10
    "奧地利",  # 10
    "of",  # 10
    "前西德",  # 9
    "几内亚",  # 9
    "巴布亚新几内亚",  # 9
    "Ecuador",  # 9
    "Paraguay",  # 9
    "印度India",  # 9
    "Mainland",  # 9
    "塞拉利昂",  # 9
    "荷蘭",  # 9
    "南极洲",  # 9
    "马其顿共和国",  # 8
    "Guinea",  # 8
    "Bangladesh",  # 8
    "印度尼西亞",  # 8
    "萨摩亚",  # 8
    "荷兰Netherlands",  # 8
    "Mongolia",  # 8
    "Macedonia",  # 8
    "Columbia",  # 8
    "新加坡Singapore",  # 8
    "斐济",  # 7
    "Ghana",  # 7
    "U.S.",  # 7
    "Panama",  # 7
    "North",  # 7
    "澳大利亚Australia",  # 7
    "the",  # 7
    "菲律賓",  # 7
    "Jordan",  # 7
    "库克群岛",  # 7
    "利比里亚",  # 6
    "Kyrgyzstan",  # 6
    "Bahamas",  # 6
    "Thailand",  # 6
    "中非",  # 6
    "Islands",  # 6
    "Turkmenistan",  # 6
    "Iraq",  # 6
    "澳大利亞",  # 6
    "Morocco",  # 6
    "蒙古国",  # 6
    "美國USA",  # 6
    "刚果(布)",  # 6
    "莱索托",  # 6
    "brazil",  # 6
    "阿曼",  # 6
    "East",  # 6
    "Luxembourg",  # 6
    "西撒哈拉",  # 6
    "Danmark",  # 6
    "泰國",  # 5
    "Papua",  # 5
    "Honduras",  # 5
    "Madagascar",  # 5
    "El",  # 5
    "Salvador",  # 5
    "English",  # 5
    "伯利兹",  # 5
    "塞尔维亚和黑山",  # 5
    "Virgin",  # 5
    "USSR",  # 5
    "Albania",  # 5
    "Yugoslavia",  # 5
    "Brasil",  # 5
    "芬蘭",  # 5
    "特立尼达和多巴哥",  # 5
    "英國UK",  # 5
    "丹麦Denmark",  # 5
    "Holland",  # 5
    "巴巴多斯",  # 5
    "Nigeria",  # 5
    "Saudi",  # 5
    "Arabia",  # 5
    "阿根廷Argentina",  # 5
    "波兰Poland",  # 5
    "俄羅斯Russia",  # 5
]


def encode_explore_queue_id(conditions: Dict[str, str]) -> str:
    """
    Convert a dictionary of conditions to a queue ID string.

    Args:
        conditions: Dictionary of condition key-value pairs

    Returns:
        A formatted queue ID string in the format "key1:value1/key2:value2/..."
        with all keys sorted alphabetically
    """
    # Sort all keys alphabetically
    sorted_keys = sorted(conditions.keys())

    # Build parts with all keys in sorted order
    parts = [f"{key}:{conditions[key]}" for key in sorted_keys]

    return "/".join(parts)


def decode_explore_queue_id(queue_id: str) -> Dict[str, str]:
    """
    Parse a queue ID string into a dictionary of conditions.

    Args:
        queue_id: A string in the format "key1:value1/key2:value2/..."

    Returns:
        Dictionary of condition key-value pairs
    """
    conditions = {}
    for condition in queue_id.split("/"):
        if ":" in condition:
            key, value = condition.split(":", 1)
            conditions[key] = value
    return conditions


def process_explore(db: Session, queue_item: Queue) -> None:
    """
    Process a queue item of type 'explore'.
    Fetches items from Douban Explore API based on conditions and saves them to DB.
    If too many results are found, creates narrower queue items.

    The queue_item.id format is expected to be
    "score_range:<range>[/condition1:value1][/condition2:value2]..."
    """
    queue_id = queue_item.id
    logger.info(f"Processing explore queue item: {queue_id}")

    # Parse conditions from queue_id
    conditions = decode_explore_queue_id(queue_id)

    # Extract item_type
    item_type = conditions.get("item_type", "movie")

    # Extract conditions
    score_range = conditions.get("score_range")
    if not score_range:
        logger.error(
            f"Invalid explore queue ID format: {queue_id} (missing score_range)"
        )
        return

    # Extract optional conditions if present
    year_range = conditions.get("year")
    type_ = conditions.get("type")
    region = conditions.get("region")

    # Prepare tags for explore API
    tags = []
    if year_range:
        tags.append(year_range)
    if type_:
        tags.append(type_)
    if region:
        tags.append(region)

    # Call explore API
    logger.info(
        f"Calling explore API with item_type={item_type},"
        f" score_range={score_range}, tags={tags}"
    )
    result = explore(item_type, score_range, tags)

    reported_total = result["total"]
    items = result["items"]

    logger.info(
        f"Found {len(items)} items (reported total {reported_total}) for {queue_id}"
    )
    if not items or reported_total == 0:
        logger.warning(
            f"No items/reported total found for explore queue item: {queue_id}."
            f" Items: {items}. Reported total: {reported_total}"
        )
        return

    # If reported total is >= NARROW_THRESHOLD,
    # add narrower conditions to the queue.
    if reported_total >= NARROW_THRESHOLD:
        if not _add_narrower_conditions(db, conditions):
            logger.warning(
                f"All conditions already present in queue item: {queue_id}."
                " No narrower conditions added."
                f" Reported total: {reported_total}"
            )

    placeholder_count = 0
    for item_detail in items:
        douban_id = item_detail["douban_id"]
        if add_placeholder_item(db, douban_id):
            placeholder_count += 1
    logger.info(f"Added {placeholder_count} placeholder items for {queue_id}")

    # NOTE: process items at last in case any error occurs during processing.
    # We don't want to lose narrower conditions or placeholder items.

    # Process retrieved items
    processed_count = 0
    for item_detail in items:
        douban_id = item_detail["douban_id"]
        existing_item = db.query(Item).filter(Item.douban_id == douban_id).first()
        if not allow_update_item(existing_item):
            continue

        # Fetch IMDb data
        imdb_info = wrap_fetch_item(
            db,
            douban_id,
            lambda douban_id=douban_id, item_detail=item_detail: fetch_imdb_id(
                douban_id, item_detail.get("in_blacklist")
            ),
        )
        if not imdb_info:
            logger.warning(f"Failed to fetch IMDb ID for douban_id={douban_id}")
            continue

        # Merge item data and save to database
        item = merge_item(item_detail, imdb_info)
        save_item_to_db(db, item)
        processed_count += 1

    logger.info(
        f"Completed processing explore queue item: {queue_id}."
        f" Processed {processed_count} items."
    )


def _add_narrower_conditions(db: Session, conditions: dict) -> bool:
    """
    Add narrower conditions based on the hierarchy:
    score_range -> year -> type -> region
    """
    year = conditions.get("year")
    type_ = conditions.get("type")
    region = conditions.get("region")

    # Determine which level of condition to add
    if not year:
        # Add year condition
        for year in YEARS:
            new_conditions = conditions.copy()
            new_conditions["year"] = year
            new_id = encode_explore_queue_id(new_conditions)
            add_to_queue(db, "explore", new_id)
            logger.info(f"Added narrower explore queue item: {new_id}")
        return True

    if not type_:
        # Add type condition
        for type_val in TYPES:
            new_conditions = conditions.copy()
            new_conditions["type"] = type_val
            new_id = encode_explore_queue_id(new_conditions)
            add_to_queue(db, "explore", new_id)
            logger.info(f"Added narrower explore queue item: {new_id}")
        return True

    if not region:
        # Add region condition
        for region_val in REGION_KEYWORDS:
            new_conditions = conditions.copy()
            new_conditions["region"] = region_val
            new_id = encode_explore_queue_id(new_conditions)
            add_to_queue(db, "explore", new_id)
            logger.info(f"Added narrower explore queue item: {new_id}")
        return True

    # If we already have all conditions, no need to add more
    return False
