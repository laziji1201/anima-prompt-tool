# -*- coding: utf-8 -*-
"""把 ffdkj 的 Danbooru 中英对照表（tag.sqlite）加工成本项目用的扩展词库。

源数据：https://github.com/ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table
        （330745 条，含 name / category / cn_name / post_count）

加工内容：
  1. 建索引：name、cn_name、post_count
  2. 把「含标点的多译名」拆成独立的行，便于逐词精确匹配
     （例如「笨蛋、测验、召唤兽」拆出「笨蛋」「测验」「召唤兽」）
  3. 生成 data/tags.sqlite，供运行时按需查询

用法：
    python tools/build_tagdb.py
    python tools/build_tagdb.py --src /path/to/tag.sqlite --out data/tags.sqlite
"""
import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "tags.sqlite"

# 拆分多译名用的分隔符
SPLIT_RE = re.compile(r"[、，,;；/|]+")


def main() -> int:
    parser = argparse.ArgumentParser(description="把原始中英对照表加工成运行时词库")
    parser.add_argument("--src", required=True, help="原始 tag.sqlite 路径（ffdkj 那份数据）")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出路径")
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.is_file():
        print(f"找不到源文件：{src}", file=sys.stderr)
        print("可从 ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table 下载 tag.sqlite", file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    print(f"源：{src}  ({src.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"输出：{out}")

    scon = sqlite3.connect(str(src))
    dcon = sqlite3.connect(str(out))
    dcur = dcon.cursor()

    dcur.execute(
        "CREATE TABLE tags ("
        "  name TEXT NOT NULL,"          # 英文 tag（下划线形式）
        "  cn TEXT NOT NULL,"            # 中文译名（已拆分为单个词）
        "  category INTEGER NOT NULL,"   # 0 常规 / 1 画师 / 3 版权 / 4 角色 / 5 元数据
        "  post_count INTEGER NOT NULL"
        ")"
    )

    rows = scon.execute(
        "SELECT name, cn_name, category, post_count FROM tags WHERE cn_name IS NOT NULL AND TRIM(cn_name) != ''"
    )

    batch: list[tuple[str, str, int, int]] = []
    n_raw = 0
    n_cn = 0
    for name, cn_name, category, count in rows:
        n_raw += 1
        name = (name or "").strip().lower()
        if not name:
            continue
        cn_name = (cn_name or "").strip()
        if not cn_name:
            continue

        pieces = [p.strip() for p in SPLIT_RE.split(cn_name)]
        pieces = [p for p in pieces if p]
        if not pieces:
            continue
        # 原文整条也保留（长译名精确匹配时优先命中）
        if len(pieces) > 1:
            pieces.append(cn_name)

        for piece in set(pieces):
            batch.append((name, piece, int(category or 0), int(count or 0)))
            n_cn += 1

        if len(batch) >= 50000:
            dcur.executemany("INSERT INTO tags VALUES (?,?,?,?)", batch)
            batch.clear()

    if batch:
        dcur.executemany("INSERT INTO tags VALUES (?,?,?,?)", batch)

    print(f"读入 {n_raw} 条，展开出 {n_cn} 条中文键")

    print("建索引…")
    dcur.execute("CREATE INDEX idx_cn ON tags(cn)")
    dcur.execute("CREATE INDEX idx_name ON tags(name)")
    dcur.execute("CREATE INDEX idx_count ON tags(post_count DESC)")
    dcon.commit()

    # 收敛体积
    dcur.execute("VACUUM")
    dcon.commit()

    total = dcur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    distinct_cn = dcur.execute("SELECT COUNT(DISTINCT cn) FROM tags").fetchone()[0]
    size = out.stat().st_size / 1024 / 1024
    print(f"完成：{total} 行，{distinct_cn} 个不同中文键，{size:.2f} MB")

    dcon.close()
    scon.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
