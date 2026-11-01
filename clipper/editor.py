"""Renderização dos cortes com ffmpeg.

- Cortes longos: 16:9 1080p, com intro/outro concatenadas se existirem em assets/.
- Shorts: 9:16 1080x1920, crop central + legendas .ass queimadas.
"""
from __future__ import annotations

import json
import random
import subprocess
from functools import lru_cache
from pathlib import Path

from .config import CONFIG, FFMPEG, ROOT


def _run(args: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {proc.stderr[-800:]}")


def _enc() -> list[str]:
    r = CONFIG["render"]
    return [
        "-c:v", "libx264", "-crf", str(r["crf"]), "-preset", r["preset"],
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    ]


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
    for piece in (intro, "MAIN", outro):
        if piece == "MAIN":
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


def _cover(w: int, h: int) -> str:
    """Preenche WxH a partir de qualquer proporção (escala e corta o excesso)."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase:"
            f"force_divisible_by=2,crop={w}:{h}")


@lru_cache(maxsize=64)
def _duration(path: str) -> float:
    ffprobe = str(Path(FFMPEG).parent / "ffprobe.exe")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0


def _loop_input(path: Path, clip_len: float) -> list[str]:
    """Input de fundo em loop, começando num ponto aleatório do vídeo.

    Se o fundo for longo o bastante, sorteia um início que caiba o corte
    inteiro (cada short fica diferente); se for curto, entra em loop do zero.
    """
    dur = _duration(str(path))
    if dur > clip_len + 2:
        offset = random.uniform(0, dur - clip_len - 1)
        return ["-ss", f"{offset:.2f}", "-i", str(path)]
    return ["-stream_loop", "-1", "-i", str(path)]


def render_short(
    src: Path,
    start: float,
    end: float,
    ass_file: Path | None,
    out: Path,
    bg: Path | None = None,
    overlay: Path | None = None,
) -> Path:
    """Short 9:16 em três variações:

    - `bg` (modo dopamina): vídeo nos 60% de cima, gameplay em loop nos 40% de
      baixo, com sombra em degradê suavizando a emenda.
    - `overlay`: fundo animado em loop preenchendo a tela, vídeo por cima um
      pouco menor, deixando borda lateral visível.
    - nenhum: crop 9:16 tradicional em tela cheia.
    """
    # O libass recebe só o nome do arquivo e o ffmpeg roda dentro da pasta dele:
    # o caminho completo (com acento, vírgula, título do episódio...) quebrava a
    # leitura da legenda em alguns PCs ("Could not create a libass track").
    ass_part = f",ass='{ass_file.name}'" if ass_file else ""
    cwd = ass_file.parent if ass_file else None

    if bg:
        top_h, bot_h, fade = 1152, 768, 220  # 60/40 de 1920; faixa do degradê
        half = fade // 2
        fc = (
            f"[0:v]{_cover(1080, top_h)},fps=30[top];"
            f"[1:v]{_cover(1080, bot_h)},fps=30[bot];"
            f"[top][bot]vstack[stk];"
            f"color=black:s=1080x{fade},format=yuva420p,"
            f"geq=lum=0:cb=128:cr=128:a='235*(1-abs(Y-{half})/{half})'[shade];"
            f"[stk][shade]overlay=0:{top_h - half},format=yuv420p{ass_part}[v]"
        )
        _run([
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
            *_loop_input(bg, end - start),
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a", "-shortest",
            *_enc(), str(out),
        ], cwd=cwd)
        return out

    if overlay:
        fc = (
            f"[1:v]{_cover(1080, 1920)},fps=30[bgv];"
            f"[0:v]{_cover(1000, 1778)},fps=30[main];"
            f"[bgv][main]overlay=(W-w)/2:(H-h)/2,format=yuv420p{ass_part}[v]"
        )
        _run([
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
            *_loop_input(overlay, end - start),
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a", "-shortest",
            *_enc(), str(out),
        ], cwd=cwd)
        return out

    vf = f"{_cover(1080, 1920)},fps=30,format=yuv420p{ass_part}"
    _run([
        "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
        "-vf", vf, *_enc(), str(out),
    ], cwd=cwd)
    return out


def extract_frame(src: Path, t: float, out: Path) -> Path:
    _run(["-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    return out
