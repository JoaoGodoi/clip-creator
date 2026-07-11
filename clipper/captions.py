"""Gera legendas .ass estilo shorts (palavra a palavra, grandes, centralizadas)."""
from __future__ import annotations

from pathlib import Path

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shorts,Arial Black,95,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

MAX_WORDS = 3
MAX_GAP = 0.6  # pausa que força quebra de bloco


def _ass_time(t: float) -> str:
    t = max(t, 0)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs % 360000 // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}"


def build_ass(words: list[dict], clip_start: float, clip_end: float, out_path: Path) -> Path:
    """Escreve o .ass com blocos de até MAX_WORDS palavras, tempos relativos ao corte."""
    clip_words = [w for w in words if w["start"] >= clip_start - 0.2 and w["end"] <= clip_end + 0.2]

    lines: list[str] = []
    block: list[dict] = []

    def flush() -> None:
        if not block:
            return
        start = block[0]["start"] - clip_start
        end = block[-1]["end"] - clip_start
        text = " ".join(w["word"] for w in block).upper().replace("{", "").replace("}", "")
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Shorts,,0,0,0,,{text}"
        )
        block.clear()

    for w in clip_words:
        if block and (len(block) >= MAX_WORDS or w["start"] - block[-1]["end"] > MAX_GAP):
            flush()
        block.append(w)
        if w["word"] and w["word"][-1] in ".!?…":
            flush()
    flush()

    out_path.write_text(ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path
