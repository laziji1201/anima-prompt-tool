# -*- coding: utf-8 -*-
"""用 PyInstaller 把程序打包成 Windows 可执行文件。

产物：
    dist/Anima提示词转换器/Anima提示词转换器.exe   主程序
    dist/Anima提示词转换器/data/tags.sqlite        扩展词库（334048 条中英对照）
    dist/Anima提示词转换器/data/Anima-preview.csv  可选，Anima tag 表（有才复制）

用 onedir 而不是 onefile：onefile 每次启动都要把几十 MB 解压到临时目录，
冷启动要好几秒；onedir 是普通目录启动，快得多。

用法：
    python tools/build_exe.py
    python tools/build_exe.py --name MyTool --onefile
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "anima_prompt.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="打包成 exe")
    parser.add_argument("--name", default="Anima提示词转换器", help="exe 名称")
    parser.add_argument("--onefile", action="store_true", help="打成单文件（启动慢）")
    parser.add_argument("--clean", action="store_true", help="先清掉 build/dist")
    args = parser.parse_args()

    if not ENTRY.is_file():
        print(f"找不到入口：{ENTRY}", file=sys.stderr)
        return 2

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("需要 PyInstaller：python -m pip install pyinstaller", file=sys.stderr)
        return 2

    if args.clean:
        for d in ("build", "dist"):
            shutil.rmtree(ROOT / d, ignore_errors=True)
        print("已清理 build/dist")

    # 图标
    icon = ROOT / "assets" / "icon.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
    ]
    if icon.is_file():
        cmd += ["--icon", str(icon)]
    cmd += [
        "--noconfirm",
        "--clean",
        "--windowed",                       # 不弹控制台
        "--onedir" if not args.onefile else "--onefile",
        "--name", args.name,
        # 只收集真正用到的模块，避免把无关的包拖进来
        "--hidden-import", "tagdb",
        "--hidden-import", "_tagtable",     # 函数内动态 import，静态分析抓不到
        "--paths", str(ROOT / "tools"),     # 让 _tagtable 可被找到
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "PIL",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PySide2",
        str(ENTRY),
    ]

    print("执行：", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("打包失败", file=sys.stderr)
        return result.returncode

    # 把数据文件放到 exe 同级
    out_dir = ROOT / "dist" / args.name
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in ("tags.sqlite", "Anima-preview.csv"):
        src = ROOT / "data" / name
        if src.is_file():
            shutil.copy2(src, data_dir / name)
            copied.append(f"{name} ({src.stat().st_size / 1024 / 1024:.1f} MB)")

    print("\n完成。产物目录：", out_dir)
    if copied:
        print("随附数据：")
        for c in copied:
            print("  -", c)
    else:
        print("注意：没有数据文件，扩展词库将不可用")

    exe = out_dir / f"{args.name}.exe"
    if exe.is_file():
        total = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
        print(f"\nexe: {exe}")
        print(f"整个目录大小：{total / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
