"""Renderização dos cortes com ffmpeg.

- Cortes longos: 16:9 1080p, com intro/outro concatenadas se existirem em assets/.
- Shorts: 9:16 1080x1920, crop central + legendas .ass queimadas.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import CONFIG, FFMPEG, ROOT


def _run(args: list[str]) -> None:
    proc = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {proc.stderr[-800:]}")


def _enc() -> list[str]:
    r = CONFIG["render"]
    return [
        "-c:v", "libx264", "-crf", str(r["crf"]), "-preset", r["preset"],
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    ]


def _filter_path(p: Path) -> str:
    """Escapa caminho Windows para uso dentro de filtros do ffmpeg."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def _asset(name: str) -> Path | None:
    p = ROOT / CONFIG["paths"]["assets"] / name
    return p if p.exists() else None


NORM = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
ANORM = "aresample=48000,aformat=channel_layouts=stereo"


def render_long(src: Path, start: float, end: float, out: Path) -> Path:
    intro, outro = _asset("intro.mp4"), _asset("outro.mp4")

    if not intro and not outro:
        _run([
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
            "-vf", NORM, *_enc(), str(out),
        ])
        return out

    inputs: list[str] = []
    chains: list[str] = []
    idx = 0
    for piece in (intro, None, outro):
        if piece is None:
            inputs += ["-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src)]
        elif piece:
            inputs += ["-i", str(piece)]
        else:
            continue
        chains.append(f"[{idx}:v]{NORM}[v{idx}];[{idx}:a]{ANORM}[a{idx}]")
        idx += 1

    pairs = "".join(f"[v{i}][a{i}]" for i in range(idx))
    fc = ";".join(chains) + f";{pairs}concat=n={idx}:v=1:a=1[v][a]"
    _run([*inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", *_enc(), str(out)])
    return out


def render_short(src: Path, start: float, end: float, ass_file: Path | None, out: Path) -> Path:
    vf = "crop=ih*9/16:ih,scale=1080:1920,fps=30,format=yuv420p"
    if ass_file:
        vf += f",ass='{_filter_path(ass_file)}'"
    _run([
        "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
        "-vf", vf, *_enc(), str(out),
    ])
    return out


def extract_frame(src: Path, t: float, out: Path) -> Path:
    _run(["-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    return out
