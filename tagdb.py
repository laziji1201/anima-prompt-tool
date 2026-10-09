# -*- coding: utf-8 -*-
"""扩展词库：把 ffdkj 的 Danbooru 中英对照表接进匹配流程。

设计要点：
  - **只做精确匹配**。实测全表 LIKE 扫描要 41ms，而 `cn = ?` 走索引只要 0.02ms。
    所以匹配方式是「在输入的每个位置，取长度 ≤ MAX_LEN 的子串去精确查一次」，
    命中就吃掉这段并发散到所有可能的起点。绝不扫表。
  - **热数据常驻内存**。启动时把 post_count 最高的一批加载成字典（毫秒级查询），
    没命中才落到 SQLite 冷查询，结果带缓存。
  - **核心词典优先**。`anima_prompt.TAG_MAP` 里手工维护并校验过的条目说了算，
    扩展词库只补它没覆盖的。

数据来源：https://github.com/ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path


def app_root() -> Path:
    """程序根目录。

    打包成 exe 后，数据放在 exe 同级目录；源码运行时就是本文件所在目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = Path(__file__).resolve().parent

# 中文译名最长取多少字参与匹配。
# 译名普遍 2-12 字，取 8 已能覆盖绝大多数；再长反而误匹配。
MAX_LEN = 8

# 启动时预载入多少条高频标签
HOT_LIMIT = 40000

# 冷查询缓存上限，防止长跑吃内存
CACHE_LIMIT = 20000

# Danbooru category
CAT_GENERAL = 0
CAT_ARTIST = 1
CAT_COPYRIGHT = 3
CAT_CHARACTER = 4
CAT_META = 5

# 标签名关键词 -> 分组。按优先级从具体到宽泛排列，先匹配到的算数。
_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("动作姿势", (
        "sitting", "standing", "lying", "kneeling", "squatting", "walking", "running",
        "jumping", "dancing", "leaning", "hugging", "holding", "carrying", "crossed_arm",
        "arm_up", "arms_", "hand_on", "hands_on", "hand_over", "legs_", "knee", "head_tilt",
        "looking_", "eyes_", "smile", "frown", "crying", "blush", "open_mouth", "closed_mouth",
        "expression", "stretching", "reaching", "pointing", "waving", "clenched",
    )),
    ("场景背景", (
        "classroom", "bedroom", "kitchen", "bathroom", "library", "hallway", "rooftop",
        "balcony", "cafe", "restaurant", "office", "shop", "hospital", "shrine", "temple",
        "castle", "ruins", "basement", "stage", "gym", "pool", "onsen", "room", "indoor",
        "outdoor", "street", "city", "alley", "park", "garden", "forest", "beach", "shore",
        "lake", "river", "mountain", "field", "grass", "desert", "sky", "cloud", "night",
        "day", "sunset", "sunrise", "rain", "snow", "fog", "cherry_blossom", "bamboo",
        "sunflower", "space", "underwater", "train", "airplane", "window", "door", "stairs",
        "mirror", "floor", "wall", "ceiling", "furniture", "bed", "couch", "chair", "table",
        "curtain", "background", "landscape", "scenery",
    )),
    ("补充细节", (
        "light", "shadow", "glow", "reflection", "bokeh", "lens_flare", "hair", "eye",
        "outfit", "dress", "shirt", "skirt", "uniform", "kimono", "sleeve", "collar",
        "necktie", "bowtie", "glove", "sock", "boot", "shoe", "hat", "cap", "scarf", "coat",
        "jacket", "sweater", "hoodie", "swimsuit", "bikini", "underwear", "jewelry",
        "earring", "necklace", "bracelet", "ring", "glasses", "mask", "ribbon", "belt",
        "wing", "tail", "horn", "halo", "ear", "chibi", "monochrome", "sketch", "watercolor",
        "from_above", "from_below", "from_behind", "from_side", "close-up", "wide_shot",
        "depth_of_field", "motion_blur", "highres", "absurdres", "aesthetic",
    )),
]


def classify(tag: str, category: int) -> str:
    """把 Danbooru 标签归到我方三分类。画家/角色/版权/元数据统一走「其他」。"""
    if category in (CAT_ARTIST, CAT_CHARACTER, CAT_COPYRIGHT):
        return "其他"
    if category == CAT_META:
        return "其他"
    name = tag.lower().replace("-", "_")
    for group, keys in _PATTERNS:
        for key in keys:
            if key in name:
                return group
    return "补充细节"      # 无法判断的常规标签，归细节，不硬猜


class TagDB:
    """扩展词库查询器。没有数据文件时静默降级，不影响纯核心词典模式。"""

    def __init__(self, path: Path | None = None):
        self.path = path or (app_root() / "data" / "tags.sqlite")
        self.hot: dict[str, list[tuple[str, int, int]]] = {}
        self.cold_cache: dict[str, list[tuple[str, int, int]]] = {}
        self.con: sqlite3.Connection | None = None
        self.available = False
        self._load()

    # ---- 装载 ----
    def _load(self) -> None:
        if not self.path.is_file():
            return
        # 只读打开，避免误写
        self.con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        cur = self.con.cursor()
        rows = cur.execute(
            "SELECT cn, name, category, post_count FROM tags "
            "ORDER BY post_count DESC LIMIT ?",
            (HOT_LIMIT,),
        )
        for cn, name, category, count in rows:
            self.hot.setdefault(cn, []).append((name, int(category), int(count)))
        self.available = True

    # ---- 查询 ----
    def lookup(self, word: str) -> list[tuple[str, int, int]]:
        """精确查一个中文词，返回 [(英文 tag, category, post_count)]，按热度降序。"""
        if not self.available or not word:
            return []
        hit = self.hot.get(word)
        if hit is not None:
            return hit
        cached = self.cold_cache.get(word)
        if cached is not None:
            return cached

        assert self.con is not None
        rows = self.con.execute(
            "SELECT name, category, post_count FROM tags WHERE cn = ? "
            "ORDER BY post_count DESC LIMIT 8",
            (word,),
        ).fetchall()
        result = [(n, int(c), int(p)) for n, c, p in rows]
        if len(self.cold_cache) < CACHE_LIMIT:
            self.cold_cache[word] = result
        return result

    def match(self, segment: str, max_len: int = MAX_LEN):
        """
        在中文片段里做「逐位置最长匹配」。

        返回 (命中列表, 未命中片段列表)：
          命中 = (中文词, 英文 tag, category, post_count, 起止下标)
        每段中文只取最高频的那一个 tag，避免一次扩张出一堆同义候选。
        """
        hits: list[tuple[str, str, int, int, int, int]] = []
        misses: list[str] = []
        i = 0
        n = len(segment)
        miss_start = -1

        def flush(end: int) -> None:
            nonlocal miss_start
            if miss_start >= 0:
                frag = segment[miss_start:end]
                if frag:
                    misses.append(frag)
                miss_start = -1

        while i < n:
            found = None
            upper = min(max_len, n - i)
            for length in range(upper, 1, -1):     # 单字不成词
                word = segment[i : i + length]
                cands = self.lookup(word)
                if cands:
                    found = (word, length, cands[0])
                    break
            if found:
                word, length, (tag, cat, count) = found
                flush(i)
                hits.append((word, tag, cat, count, i, i + length))
                i += length
            else:
                if miss_start < 0:
                    miss_start = i
                i += 1

        flush(n)
        return hits, misses

    def close(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None
