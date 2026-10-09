# -*- coding: utf-8 -*-
"""自检：把词典里的每个英文 tag 拿去 Anima 官方 tag 表核对。

用法：
    python tools/check_tags.py
    python tools/check_tags.py --tags /path/to/Anima-preview.csv
    ANIMA_TAGS=/path/to/Anima-preview.csv python tools/check_tags.py

退出码：0 = 全部命中；1 = 有 tag 不在表内；2 = 找不到 tag 表。
"""
import argparse
import csv
import sys
from pathlib import Path

# Anima 的别名列极长，默认字段上限会炸
csv.field_size_limit(64 * 1024 * 1024)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import anima_prompt as ap  # noqa: E402
import _tagtable  # noqa: E402

# 这些不是 Danbooru tag，是 Anima/Pony 系的质量词，跳过校验
QUALITY_WHITELIST = {
    "highres", "absurdres", "newest", "anime", "realistic",
    "cel shading", "watercolor", "monochrome", "retro", "pixel art",
    "chibi", "impasto",
}


def normalize(name: str) -> str:
    """Anima 表里空格/下划线两种写法混用，统一成下划线再比对。"""
    return name.strip().lower().replace(" ", "_")


def load_anima(path: Path) -> dict[str, int]:
    table: dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 3:
                continue
            name = normalize(row[0])
            if not name:
                continue
            try:
                count = int(row[2])
            except ValueError:
                continue
            table[name] = count
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description="校验词典 tag 是否都在 Anima 官方表内")
    parser.add_argument("--tags", help="Anima-preview.csv 路径")
    args = parser.parse_args()

    path = _tagtable.require(args.tags)
    print(f"tag 表：{path}")
    table = load_anima(path)
    print(f"tag 表条目：{len(table)}")

    missing: list[tuple[str, str, str]] = []
    total = 0

    for group, entries in ap.TAG_MAP.items():
        for cn, tag, _w in entries:
            total += 1
            if tag.lower() in QUALITY_WHITELIST:
                continue
            if normalize(tag) not in table:
                missing.append((group, cn, tag))

    print(f"词典条目总数：{total}")
    print(f"不在 tag 表里的：{len(missing)}")
    if missing:
        print()
        for group, cn, tag in missing:
            print(f"  [{group}] {cn}  ->  {tag}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
