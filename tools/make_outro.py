"""Gera a ending do canal (assets/outro.mp4).

Arte no estilo glitch do logo InsanoVibe (aberração cromática ciano/magenta +
fatias deslocadas), com moldura para o "próximo vídeo" e círculo do
inscreva-se — os elementos reais são encaixados na tela final do YouTube
Studio por cima dessas zonas. Fundo: partículas bokeh escurecidas; música:
massobeats - rose water (crédito obrigatório na descrição).

Rodar:  .venv\\Scripts\\python.exe tools\\make_outro.py
"""
from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipper.config import FFMPEG, ROOT  # noqa: E402

W, H = 1920, 1080
CYAN = (0, 229, 255, 255)
MAGENTA = (255, 43, 214, 255)
GREEN = (57, 255, 20, 255)
WHITE = (255, 255, 255, 255)

random.seed(42)  # arte reproduzível


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in (r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size)


def glitch_text(
    text: str,
    size: int,
    slant: float = 0.22,
    ghost: int = 8,
    slices: int = 3,
    scanlines: int = 2,
) -> Image.Image:
    """Texto com aberração cromática, fatias deslocadas e inclinação.

    Para texto pequeno use ghost 2-3, slices=0 — o efeito pesado só
    funciona em letras grandes.
    """
    font = _font(size)
    pad = 60
    bbox = font.getbbox(text)
    w, h = bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    origin = (pad - bbox[0], pad - bbox[1])

    for color, dx, dy in ((CYAN, -ghost, 0), (MAGENTA, ghost, max(ghost // 2, 1))):
        draw.text((origin[0] + dx, origin[1] + dy), text, font=font, fill=color)
    draw.text(origin, text, font=font, fill=WHITE)

    # fatias horizontais levemente deslocadas (efeito glitch)
    for _ in range(slices):
        y0 = random.randint(pad, h - pad - 10)
        band_h = random.randint(6, 12)
        shift = random.choice((-1, 1)) * random.randint(6, 12)
        band = layer.crop((0, y0, w, y0 + band_h))
        layer.paste(Image.new("RGBA", band.size, (0, 0, 0, 0)), (0, y0))
        layer.paste(band, (shift, y0), band)

    # riscos de "scanline" coloridos
    for _ in range(scanlines):
        y = random.choice((random.randint(6, pad - 6), random.randint(h - pad + 6, h - 6)))
        x = random.randint(0, w // 2)
        lw = random.randint(60, 200)
        draw.line((x, y, x + lw, y), fill=random.choice((CYAN, MAGENTA, GREEN)), width=3)

    # inclinação estilo itálico
    sheared = layer.transform(
        (w + int(h * slant), h), Image.AFFINE,
        (1, slant, -int(h * slant), 0, 1, 0), resample=Image.BICUBIC,
    )
    return sheared


def paste_center(base: Image.Image, layer: Image.Image, cx: int, cy: int) -> None:
    base.paste(layer, (cx - layer.width // 2, cy - layer.height // 2), layer)


def build_art(out_path: Path) -> Path:
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(art)

    paste_center(art, glitch_text("VALEU POR ASSISTIR!", 54, ghost=3, slices=0, scanlines=1), W // 2, 90)

    # logo empilhado à direita
    paste_center(art, glitch_text("Insano", 150, ghost=9, slices=2), 1440, 300)
    paste_center(art, glitch_text("Vibe", 150, ghost=9, slices=2), 1470, 460)

    # moldura do próximo vídeo (elemento de tela final vai por cima)
    frame = (120, 300, 952, 768)
    draw.rounded_rectangle(frame, radius=26, outline=(255, 255, 255, 210), width=5)
    draw.rounded_rectangle(
        (frame[0] + 8, frame[1] + 8, frame[2] + 8, frame[3] + 8),
        radius=26, outline=CYAN[:3] + (110,), width=3,
    )
    paste_center(art, glitch_text("PRÓXIMO VÍDEO", 44, ghost=2, slices=0, scanlines=0), (frame[0] + frame[2]) // 2, frame[1] - 46)

    # círculo do inscreva-se
    cx, cy, r = 1455, 730, 120
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 210), width=5)
    draw.ellipse((cx - r + 8, cy - r + 8, cx + r + 8, cy + r + 8), outline=MAGENTA[:3] + (110,), width=3)
    paste_center(art, glitch_text("INSCREVA-SE", 46, ghost=2, slices=0, scanlines=0), cx, cy + r + 58)

    paste_center(
        art,
        glitch_text("DEIXA O LIKE  •  COMPARTILHA  •  ATIVA O SININHO", 46, ghost=2, slices=0, scanlines=2),
        W // 2, 1000,
    )

    art.save(out_path)
    return out_path


def compose(art: Path, out: Path, duration: float = 12.0) -> None:
    bg = ROOT / "assets/overlay/particles_bokeh.mp4"
    music = ROOT / "assets/music/rose_water.m4a"
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:force_divisible_by=2,"
        f"crop={W}:{H},fps=30,eq=brightness=-0.28:saturation=0.85[bg];"
        f"[bg][1:v]overlay=0:0,fade=t=in:d=0.6,fade=t=out:st={duration - 0.9}:d=0.9,"
        f"format=yuv420p[v];"
        f"[2:a]afade=t=in:d=0.8,afade=t=out:st={duration - 1.5}:d=1.5,volume=0.9[a]"
    )
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(bg),
        "-loop", "1", "-i", str(art),
        "-ss", "14", "-i", str(music),
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-t", f"{duration}", "-c:v", "libx264", "-crf", "19", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    art = build_art(ROOT / "assets/branding/outro_art.png")
    print("arte gerada:", art)
    compose(art, ROOT / "assets/outro.mp4")
    print("ending pronta: assets/outro.mp4")
