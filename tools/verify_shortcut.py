# -*- coding: utf-8 -*-
"""点一次桌面快捷方式，确认它真能启动程序。

用法：
    python tools/verify_shortcut.py                       # 默认找「Anima 提示词转换器.lnk」
    python tools/verify_shortcut.py --lnk "别的名字.lnk"
"""
import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

DEFAULT_NAME = "Anima 提示词转换器.lnk"

# 桌面路径按系统取，不写死用户目录
DESKTOP = Path(os.path.join(os.environ.get("USERPROFILE", Path.home()), "Desktop"))
LNK = DESKTOP / DEFAULT_NAME
SHOT = Path(__file__).resolve().parent.parent / "docs" / "界面-空态.png"

ctypes.windll.shcore.SetProcessDpiAwareness(1)
u = ctypes.windll.user32
g = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


def find_window(part: str, timeout: float = 25.0):
    end = time.time() + timeout
    while time.time() < end:
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(h, _l):
            n = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(h, n, 512)
            if part in n.value and u.IsWindowVisible(h):
                found.append(h)
            return True

        u.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.4)
    return None


def capture(hwnd, path: Path) -> None:
    r = RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.r - r.l, r.b - r.t
    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)
    u.PrintWindow(hwnd, mem, 2)

    class BIH(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    print(f"截图已保存 {path}  {w}x{h}")
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, hdc)


def main() -> int:
    parser = argparse.ArgumentParser(description="点一次桌面快捷方式，验证它能否启动程序")
    parser.add_argument("--lnk", help=f"快捷方式文件名，默认 {DEFAULT_NAME}")
    parser.add_argument("--no-shot", action="store_true", help="只验证启动，不截图")
    args = parser.parse_args()

    lnk = (DESKTOP / args.lnk) if args.lnk else LNK
    if not lnk.exists():
        print(f"快捷方式不存在：{lnk}")
        return 1

    print(f"存在：{lnk}")
    os.startfile(str(lnk))  # 等价于双击

    hwnd = find_window("Anima 中文提示词转换器")
    if not hwnd:
        print("点了快捷方式，但 25 秒内没等到窗口 —— 快捷方式有问题")
        return 1

    print("窗口已起来，快捷方式可用")
    if not args.no_shot:
        time.sleep(2.5)
        capture(hwnd, SHOT)

    u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
