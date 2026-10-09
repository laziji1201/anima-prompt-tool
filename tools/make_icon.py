# -*- coding: utf-8 -*-
"""生成应用图标：青绿圆角底 + 白色羽毛笔 + 墨点。

用法：python tools/make_icon.py
输出：assets/icon.ico（多尺寸）、assets/icon.png（预览）
需要 Pillow，仅构建期使用，运行时不依赖。
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

ACCENT = (15, 82, 87)       # #0F5257，与界面强调色一致
ACCENT_HI = (32, 116, 122)
INK = (255, 255, 255)

S = 512
SS = 4  # 超采样倍数，先画大再缩，边缘更干净
W = S * SS

img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

# ---- 圆角底：竖向微渐变，不做花哨渐变，只让底部沉一点 ----
grad = Image.new("RGBA", (W, W), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(W):
    t = y / W
    col = tuple(int(ACCENT[i] + (ACCENT_HI[i] - ACCENT[i]) * (1 - t)) for i in range(3))
    gd.line([(0, y), (W, y)], fill=col + (255,))

mask = Image.new("L", (W, W), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.22), fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)

# ---- 羽毛笔：羽片（旋转椭圆）+ 笔轴 + 墨点 ----
# 几何：笔尖在右下，羽片在左上，墨点在笔尖右侧
def pt(x: float, y: float) -> tuple[float, float]:
    return (x * W, y * W)


# ---- 羽毛笔 ----
# 图标要在 16px 下也认得出，所以只保留三个视觉要素：
#   细长羽片、一笔长笔画、末尾落墨。不做羽枝等细节——缩到小尺寸只会糊成噪点。
ANG = math.radians(42)                      # 笔画走向：左上 → 右下
UX, UY = math.cos(ANG), math.sin(ANG)
VX, VY = -UY, UX                            # 垂直于笔画，指向羽片那侧

# 羽片：主轴 + 上下两条弧线围成的叶形，两端收尖
FX, FY = 0.27, 0.27                         # 羽片中心
F_LEN, F_WID = 0.185, 0.056                 # 半长 / 半宽

def fpt(t: float, w: float) -> tuple[float, float]:
    """t∈[-1,1] 沿羽片主轴，w 为垂直偏移。"""
    return pt(FX + t * F_LEN * UX + w * VX, FY + t * F_LEN * UY + w * VY)

poly = []
STEPS = 64
for i in range(STEPS + 1):                  # 上缘：根部 → 尖端
    t = -1 + 2 * i / STEPS
    wide = F_WID * (1 - abs(t) ** 1.7)      # 中间最宽，两端收尖
    poly.append(fpt(t, wide))
for i in range(STEPS + 1):                  # 下缘：尖端 → 根部
    t = 1 - 2 * i / STEPS
    wide = F_WID * 0.42 * (1 - abs(t) ** 1.7)
    poly.append(fpt(t, -wide))
d.polygon(poly, fill=INK)

# 笔画：从羽片根部一路写到右下，末端是笔尖
d.line([fpt(-1.02, -0.004), pt(0.70, 0.66)], fill=INK, width=int(W * 0.030))

# 落墨：笔尖前方一点，让「在写」这个动作成立
ink = pt(0.775, 0.725)
d.ellipse(
    [ink[0] - W * 0.034, ink[1] - W * 0.034, ink[0] + W * 0.034, ink[1] + W * 0.034],
    fill=INK,
)

# ---- 缩回目标尺寸 ----
icon = img.resize((S, S), Image.LANCZOS)

ico = OUT / "icon.ico"
icon.save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
print(f"已生成 {ico}")
print(f"已生成 {OUT / 'icon.png'}")
