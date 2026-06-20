from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]


def generate_covers(day_dir: Path, now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {"success": False, "files": [], "warning": ""}
    try:
        square = day_dir / "cover_square.png"
        vertical = day_dir / "cover_vertical.png"
        render_cover(square, (1080, 1080), now)
        render_cover(vertical, (1080, 1920), now)
        result.update({"success": True, "files": [str(square), str(vertical)]})
    except Exception as exc:
        result["warning"] = f"封面生成失败：{exc}"
    return result


def render_cover(path: Path, size: tuple[int, int], now: datetime) -> None:
    width, height = size
    image = Image.new("RGB", size, "#eef5fb")
    draw = ImageDraw.Draw(image)

    # Original geometric artwork: morning horizon, signal lines and news panels.
    draw.rectangle((0, 0, width, int(height * 0.42)), fill="#dbeaf6")
    draw.ellipse((int(width * 0.62), int(height * 0.06), int(width * 0.91), int(height * 0.23)), fill="#f2c86f")
    draw.arc((int(width * 0.52), int(height * 0.18), int(width * 1.05), int(height * 0.55)), 190, 345, fill="#6d91ad", width=4)
    draw.arc((int(width * 0.44), int(height * 0.14), int(width * 1.12), int(height * 0.61)), 190, 345, fill="#9bb6ca", width=3)

    panel_top = int(height * 0.47)
    draw.rounded_rectangle((70, panel_top, width - 70, height - 90), radius=24, fill="#f9fbfd", outline="#b8cad8", width=2)
    for index, bar_width in enumerate((390, 620, 510)):
        y = panel_top + 240 + index * 55
        draw.rounded_rectangle((110, y, 110 + bar_width, y + 18), radius=9, fill="#c8d9e5")

    regular = font(38)
    small = font(28)
    title = font(76 if height <= 1080 else 86, bold=True)
    draw.text((82, 75), "PRIVATE INTELLIGENCE RADIO", font=small, fill="#34556e")
    draw.text((82, int(height * 0.27)), "我的 AI\n早餐情报电台", font=title, fill="#18384f", spacing=18)
    draw.text((110, panel_top + 70), "每天早上，AI 自动生成一份", font=regular, fill="#34556e")
    draw.text((110, panel_top + 125), "国际新闻与商业趋势音频", font=regular, fill="#34556e")
    draw.text((110, height - 180), f"{now:%Y.%m.%d}  |  为小乌生成", font=small, fill="#6a7e8d")
    draw.text((110, height - 135), "AI Workflow Demo | Private Intelligence Radio", font=font(21), fill="#8295a3")
    image.save(path, "PNG", optimize=True)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = FONT_CANDIDATES[1:] + FONT_CANDIDATES[:1] if bold else FONT_CANDIDATES
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()
