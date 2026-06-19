# -*- coding: utf-8 -*-
"""每日一言模块 —— 联网-离线循环
- 启动时尝试从 hitokoto API 拉取新句追加到本地池
- 断网时从本地池 / 内置语料随机取
- 基于日期 hash 确保同一天取同一条
"""
import hashlib
import json
import os
import random
import time
from datetime import date

import urllib.request
import urllib.error

# ---------- 内置语料 (30条) ----------
BUILTIN_QUOTES = [
    {"content": "科学的每一项巨大成就，都是以大胆的幻想为出发点的。", "author": "杜威"},
    {"content": "想象力比知识更重要，因为知识是有限的，而想象力概括着世界的一切。", "author": "爱因斯坦"},
    {"content": "在科学上没有平坦的大道，只有不畏劳苦沿着陡峭山路攀登的人，才有希望达到光辉的顶点。", "author": "马克思"},
    {"content": "如果说我比别人看得更远些，那是因为我站在了巨人的肩上。", "author": "牛顿"},
    {"content": "人的天职在于勇于探索真理。", "author": "哥白尼"},
    {"content": "一个从未犯错的人是因为他不曾尝试新鲜事物。", "author": "爱因斯坦"},
    {"content": "实验是检验真理的唯一标准。", "author": "佚名"},
    {"content": "提出一个问题往往比解决一个问题更重要。", "author": "爱因斯坦"},
    {"content": "我不知道世人怎样看我，但我自己以为我不过像一个在海边玩耍的孩子，不时为发现一块光滑的卵石或一片美丽的贝壳而沾沾自喜。", "author": "牛顿"},
    {"content": "知识就是力量。", "author": "培根"},
    {"content": "真理的大海，让未发现的一切事物躺卧在我的眼前，任我去探寻。", "author": "牛顿"},
    {"content": "我平生从来没有做出过一次偶然的发明。我的一切发明都是经过深思熟虑和严格试验的结果。", "author": "爱迪生"},
    {"content": "在科学的世界里，质疑不是亵渎，而是进步的阶梯。", "author": "佚名"},
    {"content": "不要等待，时机永远不会恰到好处。", "author": "拿破仑"},
    {"content": "我们反复做的事情造就了我们。卓越不是一种行为，而是一种习惯。", "author": "亚里士多德"},
    {"content": "你可以从别人那里得来思想，你的思想方法，即熔铸思想的模子，必须是你自己的。", "author": "拉姆"},
    {"content": "学习的本质不在于记住哪些知识，而在于它触发了你的思考。", "author": "迈克尔·桑德尔"},
    {"content": "世界上没有笨人，只有被动的学习。", "author": "佚名"},
    {"content": "测量即认知。", "author": "开尔文"},
    {"content": "每一个伟大的实验背后，都有一个敢于提问的灵魂。", "author": "佚名"},
    {"content": "所有的模型都是错的，但有些是有用的。", "author": "乔治·博克斯"},
    {"content": "物理学是研究万物运行规律的科学，而好奇心是驱动它的燃料。", "author": "费曼"},
    {"content": "在你理解一个事物之前，你无法确信自己能否把它简化。", "author": "佚名"},
    {"content": "天才是百分之一的灵感加上百分之九十九的汗水。", "author": "爱迪生"},
    {"content": "成功不是终点，失败也并非末日，最重要的是继续前进的勇气。", "author": "丘吉尔"},
    {"content": "纸上得来终觉浅，绝知此事要躬行。", "author": "陆游"},
    {"content": "不积跬步，无以至千里；不积小流，无以成江海。", "author": "荀子"},
    {"content": "业精于勤，荒于嬉；行成于思，毁于随。", "author": "韩愈"},
    {"content": "宝剑锋从磨砺出，梅花香自苦寒来。", "author": "佚名"},
    {"content": "滴水穿石，不是力量大，而是功夫深。", "author": "佚名"},
]

# ---------- 路径 ----------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
QUOTES_POOL_FILE = os.path.join(DATA_DIR, "daily_quotes.json")
HITOKOTO_URL = "https://v1.hitokoto.cn/"
FETCH_COUNT = 2
FETCH_TIMEOUT = 2


def _load_pool():
    """加载本地语料池"""
    if not os.path.exists(QUOTES_POOL_FILE):
        return []
    try:
        with open(QUOTES_POOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_pool(quotes_list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(QUOTES_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(quotes_list, f, ensure_ascii=False, indent=2)


def fetch_online_quotes(count=FETCH_COUNT):
    """联网从 hitokoto API 拉取句子，去重后追加到本地池。超时或异常静默失败。"""
    new_quotes = []
    for _ in range(count):
        try:
            req = urllib.request.Request(HITOKOTO_URL, headers={"User-Agent": "PhysicsQuiz/0.8.2"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("hitokoto", "").strip()
                author = (data.get("from", "") or "佚名").strip()
                if content:
                    new_quotes.append({"content": content, "author": author})
        except Exception:
            break
    if not new_quotes:
        return
    pool = _load_pool()
    existing = {(q["content"], q["author"]) for q in pool}
    for q in new_quotes:
        key = (q["content"], q["author"])
        if key not in existing:
            pool.append(q)
            existing.add(key)
    _save_pool(pool)


def get_daily_quote():
    """返回当日一言 (content, author)。
    优先从本地池取，池空则用内置语料。
    基于日期 hash 保证同一天取同一条。
    """
    today = date.today().isoformat()
    pool = _load_pool()
    source = pool if pool else BUILTIN_QUOTES
    index = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(source)
    q = source[index]
    return q["content"], q["author"]
