"""Thumbnail 1280x720: frame do vídeo + faixa escura + texto de impacto."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\impact.ttf",
    r"C:\Windows\Fonts\ariblk.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def make_thumbnail(frame_path: Path, text: str, out_path: Path) -> Path:
    img = Image.open(frame_path).convert("RGB")
    img = img.resize((1280, 720))
    img = ImageEnhance.Contrast(img).enhance(1.1)

    draw = ImageDraw.Draw(img, "RGBA")
    text = (text or "").upper().strip()
    if text:
        lines = textwrap.wrap(text, width=16)[:3]
        font = _font(110 if len(lines) <= 2 else 88)
        line_h = font.size + 14
        total_h = line_h * len(lines)
        y0 = 720 - total_h - 60

        draw.rectangle([(0, y0 - 40), (1280, 720)], fill=(0, 0, 0, 160))
        y = y0 - 10
        for line in lines:
            w = draw.textlength(line, font=font)
            x = (1280 - w) / 2
            draw.text((x, y), line, font=font, fill="#FFD400",
                      stroke_width=8, stroke_fill="black")
            y += line_h

    img.save(out_path, "JPEG", quality=90)
    return out_path
