# -*- coding: utf-8 -*-
"""统计：33 万条对照表里，有多少落在 Anima 官方 tag 表内。

决定扩展词库的产出层级：
  - 在 Anima 表内 -> 可作硬 tag 直接进 prompt
  - 不在表内     -> 只能作候选展示，不进 prompt（Anima 不认识）
"""
import csv
import sqlite3
import sys
from pathlib import Path

csv.field_size_limit(64 * 1024 * 1024)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _tagtable  # noqa: E402

DB = ROOT / "data" / "tags.sqlite"


def normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def load_anima(path: Path) -> set[str]:
    out = set()
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 3:
                out.add(normalize(row[0]))
    return out


def main() -> int:
    anima_path = _tagtable.find()
    if anima_path is None:
        print("没有 Anima tag 表，跳过")
        return 1
    anima = load_anima(anima_path)
    print(f"Anima 表：{len(anima)} 条")

    con = sqlite3.connect(str(DB))
    cur = con.cursor()

    total = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    distinct_name = cur.execute("SELECT COUNT(DISTINCT name) FROM tags").fetchone()[0]
    print(f"扩展词库：{total} 行，{distinct_name} 个不同英文 tag")

    names = [n for (n,) in cur.execute("SELECT DISTINCT name FROM tags")]
    in_anima = [n for n in names if normalize(n) in anima]
    print(f"\n不同英文 tag 中，在 Anima 表内：{len(in_anima)} / {len(names)}"
          f"  ({len(in_anima)/len(names)*100:.1f}%)")

    # 按热度看：高频词里有多少被 Anima 认识
    print("\n=== 高频段落的覆盖 ===")
    for th in (10000, 5000, 1000, 100, 0):
        rows = cur.execute(
            "SELECT DISTINCT name FROM tags WHERE post_count >= ?", (th,)
        ).fetchall()
        names_at = [n for (n,) in rows]
        ok = sum(1 for n in names_at if normalize(n) in anima)
        pct = ok / len(names_at) * 100 if names_at else 0
        print(f"  post_count >= {th:>6}: {ok:>6} / {len(names_at):>6}  ({pct:5.1f}%)")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
