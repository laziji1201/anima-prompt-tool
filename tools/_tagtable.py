# -*- coding: utf-8 -*-
"""定位 Anima 官方 tag 表（Anima-preview.csv）。

开源项目不能写死开发机路径，所以按优先级查找：
  1. 命令行 --tags <path>
  2. 环境变量 ANIMA_TAGS
  3. 项目内自带副本 data/Anima-preview.csv
  4. 常见 ComfyUI / 技能包位置
  5. 项目相邻目录

找不到就报清楚，并告诉用户去哪里拿。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILENAME = "Anima-preview.csv"

# 项目内自带副本优先，保证 clone 下来开箱可用
LOCAL_CANDIDATES = [
    ROOT / "data" / FILENAME,
    ROOT / FILENAME,
]

# 常见安装位置（用户本机已有 ComfyUI 技能包时直接复用）
COMMON_CANDIDATES = [
    Path(r"D:\comfyui\skills\comfyui-good-anima-main\danbooru-tags") / FILENAME,
    Path.home() / "comfyui" / "skills" / "comfyui-good-anima-main" / "danbooru-tags" / FILENAME,
    Path.home() / "Documents" / "comfyui" / "danbooru-tags" / FILENAME,
    ROOT.parent / "danbooru-tags" / FILENAME,
]

HINT = (
    "需要 Anima 官方 tag 表 Anima-preview.csv，三种拿法：\n"
    "  1. 把 CSV 放到 data/Anima-preview.csv（推荐）\n"
    "  2. 设环境变量 ANIMA_TAGS=<csv 路径>\n"
    "  3. 命令加参数 --tags <csv 路径>\n"
    "来源：ComfyUI 的 Anima 技能包，或 "
    "https://github.com/ComfyNodePRs/PR-Comfyui-Anima-tools-a0fe04bd"
)


def find(explicit: str | None = None) -> Path | None:
    """按优先级返回 tag 表路径；都找不到返回 None。"""
    # 1. 命令行
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None

    # 2. 环境变量
    env = os.environ.get("ANIMA_TAGS")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p

    # 3. 项目内自带
    for p in LOCAL_CANDIDATES:
        if p.is_file():
            return p

    # 4. 常见位置
    for p in COMMON_CANDIDATES:
        if p.is_file():
            return p

    return None


def require(explicit: str | None = None) -> Path:
    """同上，但找不到就打印提示并退出。"""
    path = find(explicit)
    if path is None:
        print(HINT, file=sys.stderr)
        raise SystemExit(2)
    return path
