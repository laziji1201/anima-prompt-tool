# -*- coding: utf-8 -*-
"""制作 GitHub Release 用的 zip 包。

要点：
  - onedir 打包的 exe 依赖同级的 _internal/（Python 运行时和 DLL），
    必须整个目录一起发，只发 exe 是跑不起来的。
  - 刻意排除 Anima-preview.csv：它出自 GPL-3.0 项目，不能再分发。
    发布包只带 MIT 许可的扩展词库 tags.sqlite。

用法：
    python tools/make_release.py
    python tools/make_release.py --version v0.2.0
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "Anima提示词转换器"
RELEASE_DIR = ROOT / "release"

# 绝不打包：授权不允许
FORBIDDEN = ["Anima-preview.csv", "Anima-preview-alternate.csv"]

# 从 dist 里排除的临时/无关文件
DIST_EXCLUDE = {"anima_debug.txt"}


def main() -> int:
    parser = argparse.ArgumentParser(description="制作发布 zip")
    parser.add_argument("--version", default="v0.2.0", help="版本号")
    parser.add_argument(
        "--zip-name",
        default="",
        help="zip 文件名（默认 anima-prompt-tool-<版本>-win64.zip）",
    )
    args = parser.parse_args()

    if not DIST.is_dir():
        print(f"找不到打包产物：{DIST}\n先跑 python tools/build_exe.py", file=sys.stderr)
        return 2

    exe = DIST / "Anima提示词转换器.exe"
    if not exe.is_file():
        print(f"找不到 exe：{exe}", file=sys.stderr)
        return 2

    # onedir 的 exe 离不开 _internal/，缺了就直接跑不起来
    internal = DIST / "_internal"
    if not internal.is_dir():
        print(f"[错误] 缺少 {internal}，onedir 产物不完整", file=sys.stderr)
        return 1

    stage = RELEASE_DIR / f"Anima提示词转换器-{args.version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    # 1. 整个 dist 目录照搬（含 _internal），排除临时文件和授权受限数据
    n_dist = 0
    for src in sorted(DIST.rglob("*")):
        if not src.is_file():
            continue
        if src.name in DIST_EXCLUDE or any(f == src.name for f in FORBIDDEN):
            print(f"[排除] {src.relative_to(DIST)}")
            continue
        dst = stage / src.relative_to(DIST)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n_dist += 1

    # 2. 补上说明文档
    extra = []
    for name in ("README.md", "LICENSE"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, stage / name)
            extra.append(name)

    # 3. 空词库占位，让用户知道往哪加自己的映射
    ud = stage / "data" / "user_dict.json"
    ud.parent.mkdir(parents=True, exist_ok=True)
    if not ud.exists():
        ud.write_text("{}\n", encoding="utf-8")

    # zip 用 ASCII 文件名：中文名在传输链路上容易被编码破坏
    # （实测上传到 GitHub 后变成 "Anima.-v0.2.0.zip"）
    zip_name = args.zip_name or f"anima-prompt-tool-{args.version}-win64.zip"
    zip_path = RELEASE_DIR / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(stage.parent))

    total = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file())
    print(f"产物目录：{stage}")
    print(f"  程序文件 {n_dist} 个（含 _internal/）+ 文档 {'、'.join(extra)}")
    print(f"  解压后 {total / 1024 / 1024:.1f} MB")
    print(f"\nzip：{zip_path.name}  ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # 自检：授权受限数据不能进包，关键运行文件必须在
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    bad = [n for n in names if any(f in n for f in FORBIDDEN)]
    if bad:
        print(f"\n[错误] 发布包里出现了不该有的文件：{bad}", file=sys.stderr)
        return 1
    for must in ("Anima提示词转换器.exe", "_internal/python313.dll", "data/tags.sqlite"):
        if not any(n.endswith(must) for n in names):
            print(f"\n[错误] 发布包缺少运行所需文件：{must}", file=sys.stderr)
            return 1
    print(f"自检通过：{len(names)} 个文件；不含 GPL 授权的 tag 表；运行所需文件齐全")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
