# -*- coding: utf-8 -*-
"""针对词典里「不在 Anima 表内」的 tag，反查表里的近似候选。

用法：
    python tools/suggest_fixes.py
    python tools/suggest_fixes.py --tags /path/to/Anima-preview.csv

输出：每个未命中的 tag 配上按 post_count 降序的候选，供人工决定换成什么。
"""
import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(64 * 1024 * 1024)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import anima_prompt as ap  # noqa: E402
import _tagtable  # noqa: E402

QUALITY_WHITELIST = {
    "highres", "absurdres", "newest", "anime", "realistic",
    "cel shading", "watercolor", "monochrome", "retro", "pixel art",
    "chibi", "impasto",
}


def normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def load_anima(path: Path) -> dict[str, int]:
    table: dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 3:
                continue
            name = normalize(row[0])
            try:
                count = int(row[2])
            except ValueError:
                continue
            table[name] = count
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description="为不在表内的 tag 反查近似候选")
    parser.add_argument("--tags", help="Anima-preview.csv 路径")
    parser.add_argument("--top", type=int, default=5, help="每个 tag 显示多少候选，默认 5")
    args = parser.parse_args()

    path = _tagtable.require(args.tags)
    table = load_anima(path)
    print(f"tag 表：{path}（{len(table)} 条）\n")

    found_any = False
    for group, entries in ap.TAG_MAP.items():
        for cn, tag, _w in entries:
            tl = tag.lower()
            if tl in QUALITY_WHITELIST or normalize(tag) in table:
                continue

            found_any = True
            words = [w for w in tl.replace("_", " ").split() if len(w) > 2]
            cands: list[tuple[int, str]] = []
            for name, count in table.items():
                flat = name.replace("_", " ")
                if words and all(w in flat for w in words):
                    cands.append((count, name))
            cands.sort(reverse=True)

            print(f"[{group}] {cn}  ->  {tag}")
            if cands:
                for count, name in cands[: args.top]:
                    print(f"      {name}  ({count})")
            else:
                print("      （无候选，考虑改写成自然语言短语）")
            print()

    if not found_any:
        print("词典里所有 tag 都在表内，无需修正。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
