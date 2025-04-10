from datetime import datetime
import logging
from sqlalchemy.orm import Session
from typing import Dict

from app.models import Item, Queue, add_placeholder_item, add_to_queue
from app.info_provider.explore import explore
from app.info_provider.imdb import fetch_imdb_id
from app.queue_processor.common import allow_update_item, merge_item, save_item_to_db

logger = logging.getLogger(__name__)

COUNT = 500

# Score ranges for exploration. Higher scores come first.
SCORE_RANGES = [f"{i},{i+1}" for i in range(9, -1, -1)]

# Predefined conditions for narrowing down exploration

# Years from 1980 to current year + 5. Later years come first.
YEARS = [str(year) for year in range(datetime.now().year + 5, 1979, -1)]
# Years before 1980. We expect fewer items in these ranges.
YEARS += ["70年代", "60年代", "更早"]

# Based on existing data in database
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
REGIONS = [
    "美国",  # 79522
    "中国大陆",  # 39836
    "日本",  # 32223
    "英国",  # 21354
    "法国",  # 19181
    "中国香港",  # 11680
    "韩国",  # 9656
    "德国",  # 9461
    "意大利",  # 8916
    "加拿大",  # 7801
    "中国台湾",  # 7205
    "印度",  # 5762
    "西班牙",  # 5703
    "澳大利亚",  # 2907
    "泰国",  # 2851
    "巴西",  # 2734
    "瑞典",  # 2667
    "俄罗斯",  # 2537
    "丹麦",  # 1945
    "比利时",  # 1715
    "西德",  # 1509
    "墨西哥",  # 1474
    "阿根廷",  # 1376
    "苏联",  # 1346
    "波兰",  # 1317
    "荷兰",  # 1254
    "瑞士",  # 1116
    "爱尔兰",  # 915
    "奥地利",  # 915
    "伊朗",  # 859
    "捷克斯洛伐克",  # 840
    "菲律宾",  # 832
    "匈牙利",  # 800
    "挪威",  # 739
    "土耳其",  # 717
    "芬兰",  # 616
    "以色列",  # 606
    "新加坡",  # 601
    "葡萄牙",  # 584
    "捷克",  # 558
    "罗马尼亚",  # 530
    "南斯拉夫",  # 520
    "新西兰",  # 415
    "希腊",  # 414
    "南非",  # 358
    "智利",  # 321
    "印度尼西亚",  # 278
    "保加利亚",  # 272
    "哥伦比亚",  # 250
    "卢森堡",  # 247
    "马来西亚",  # 242
    "冰岛",  # 234
    "乌克兰",  # 218
    "古巴",  # 185
    "中国",  # 174
    "越南",  # 169
    "克罗地亚",  # 169
    "塞尔维亚",  # 158
    "爱沙尼亚",  # 149
    "埃及",  # 143
    "委内瑞拉",  # 121
    "摩洛哥",  # 107
    "立陶宛",  # 104
    "卡塔尔",  # 104
    "斯洛文尼亚",  # 103
    "黎巴嫩",  # 98
    "格鲁吉亚",  # 95
    "秘鲁",  # 94
    "乌拉圭",  # 90
    "阿尔及利亚",  # 89
    "拉脱维亚",  # 87
    "斯洛伐克",  # 87
    "突尼斯",  # 81
    "哈萨克斯坦",  # 78
    "阿尔巴尼亚",  # 71
    "波黑",  # 61
    "朝鲜",  # 56
    "阿联酋",  # 53
    "东德",  # 47
    "巴基斯坦",  # 44
    "蒙古",  # 41
    "柬埔寨",  # 41
    "伊拉克",  # 40
    "斯里兰卡",  # 38
    "马其顿",  # 38
    "波多黎各",  # 38
    "阿富汗",  # 38
    "塞内加尔",  # 37
    "多米尼加",  # 37
    "亚美尼亚",  # 36
    "香港",  # 35
    "巴勒斯坦",  # 34
    "中国澳门",  # 33
    "尼日利亚",  # 33
    "约旦",  # 30
    "叙利亚",  # 30
    "玻利维亚",  # 28
    "哥斯达黎加",  # 28
    "布基纳法索",  # 26
    "白俄罗斯",  # 26
    "厄瓜多尔",  # 26
    "阿塞拜疆",  # 26
    "俄羅斯",  # 26
    "马耳他",  # 25
    "尼泊尔",  # 25
    "印尼",  # 25
    "巴拿马",  # 24
    "科索沃",  # 24
    "沙特阿拉伯",  # 23
    "塞浦路斯",  # 21
    "孟加拉国",  # 21
    "缅甸",  # 21
    "摩纳哥",  # 20
    "列支敦士登",  # 19
    "台灣",  # 19
    "北马其顿",  # 18
    "埃塞俄比亚",  # 17
    "吉尔吉斯斯坦",  # 16
    "肯尼亚",  # 16
    "前苏联",  # 16
    "喀麦隆",  # 15
    "英國",  # 15
    "危地马拉",  # 14
    "塞黑",  # 13
    "巴拉圭",  # 13
    "尼加拉瓜",  # 13
    "津巴布韦",  # 12
    "乌兹别克斯坦",  # 12
    "马里",  # 12
    "原西德",  # 11
    "乍得",  # 11
    "德國",  # 11
    "俄国",  # 10
    "老挝",  # 10
    "加拿大Canada",  # 10
    "不丹",  # 10
    "蘇聯",  # 10
    "孟加拉",  # 10
    "丹麥",  # 10
    "加纳",  # 9
    "毛里塔尼亚",  # 9
    "刚果",  # 9
    "科威特",  # 8
    "塔吉克斯坦",  # 8
    "多米尼加共和国",  # 8
    "澳洲",  # 8
    "印度India",  # 8
    "黑山",  # 8
    "尼日尔",  # 7
    "美國",  # 7
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
    result = explore(item_type, score_range, tags, count=COUNT)

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

    # If reported total is large or items are less than 95% of reported total,
    # add narrower conditions to the queue.
    if reported_total > 400 or len(items) / reported_total < 0.95:
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
        imdb_info = fetch_imdb_id(douban_id, item_detail.get("in_blacklist"))
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
        for region_val in REGIONS:
            new_conditions = conditions.copy()
            new_conditions["region"] = region_val
            new_id = encode_explore_queue_id(new_conditions)
            add_to_queue(db, "explore", new_id)
            logger.info(f"Added narrower explore queue item: {new_id}")
        return True

    # If we already have all conditions, no need to add more
    return False
