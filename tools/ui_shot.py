# -*- coding: utf-8 -*-
"""用 PrintWindow 抓窗口自身内容（被遮挡也能抓），用于 UI 验收。"""
import ctypes
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "docs"

ctypes.windll.shcore.SetProcessDpiAwareness(1)
u = ctypes.windll.user32
g = ctypes.windll.gdi32


def shot_dir() -> Path:
    return SHOT_DIR


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


def find(hwnd_title: str, pid: int | None = None, timeout: float = 25.0):
    """按标题找可见窗口；给了 pid 就只认该进程的窗口。

    只按标题找会撞上上一次测试没退干净的同名窗口，截到空态。
    """
    end = time.time() + timeout
    while time.time() < end:
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(h, _l):
            n = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(h, n, 512)
            if hwnd_title not in n.value or not u.IsWindowVisible(h):
                return True
            if pid is not None:
                owner = ctypes.c_ulong()
                u.GetWindowThreadProcessId(h, ctypes.byref(owner))
                if owner.value != pid:
                    return True
            found.append(h)
            return True

        u.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.3)
    return None


def capture(hwnd, path: Path) -> None:
    r = RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.r - r.l, r.b - r.t

    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)

    # PW_RENDERFULLCONTENT = 2：能抓到被遮挡/未置前的窗口
    u.PrintWindow(hwnd, mem, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h  # 负值 = 自上而下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    print(f"已保存 {path}  {w}x{h}")

    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, hdc)


def main() -> int:
    # 用法：python ui_shot.py [--expand] [--exe] [--text "文本"] [输出文件名]
    argv = sys.argv[1:]
    expand = "--expand" in argv
    use_exe = "--exe" in argv

    demo_text = None
    if "--text" in argv:
        i = argv.index("--text")
        if i + 1 < len(argv):
            demo_text = argv[i + 1]
            argv = argv[:i] + argv[i + 2 :]

    args = [a for a in argv if not a.startswith("--")]
    default_name = "界面-展开分类.png" if expand else "界面-折叠.png"
    name = args[0] if args else default_name
    shot = shot_dir() / name

    if use_exe:
        exe = ROOT / "dist" / "Anima提示词转换器" / "Anima提示词转换器.exe"
        if not exe.is_file():
            print(f"找不到 exe：{exe}\n先跑 python tools/build_exe.py")
            return 1
        cmd = [str(exe), "--demo"]
        workdir = str(exe.parent)
    else:
        cmd = [sys.executable, "-X", "utf8", str(ROOT / "anima_prompt.py"), "--demo"]
        workdir = str(ROOT)

    if demo_text:
        cmd.append(demo_text)
    if expand:
        cmd.append("--expand")

    shot.parent.mkdir(parents=True, exist_ok=True)
    print(f"启动：{cmd[0]}")
    if demo_text:
        print(f"文本：{demo_text}")
    proc = subprocess.Popen(cmd, cwd=workdir)
    try:
        # 必须限定 pid，否则会撞上残留的同名窗口
        hwnd = find("Anima 中文提示词转换器", pid=proc.pid)
        if not hwnd:
            print("没找到窗口")
            return 1
        time.sleep(3.0)  # 等自动转换（和展开）跑完；exe 冷启动更慢
        capture(hwnd, shot)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
