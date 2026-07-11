"""Seleção dos melhores cortes via LLM (Claude) sobre a transcrição.

Sem ANTHROPIC_API_KEY, gera cortes "mock" (janelas uniformes) apenas para
testar o restante do pipeline.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

from .config import CONFIG

PROMPT = """Você é um editor de cortes de podcast experiente. Abaixo está a transcrição \
de um episódio, com o timestamp de início de cada fala.

Título do episódio: {video_title}
Podcast: {podcast}
Duração total: {duration_min:.0f} minutos

Selecione:
1. {n_long} CORTES LONGOS de {long_min} a {long_max} minutos — blocos temáticos coesos \
que funcionam como vídeo independente no YouTube (uma história completa, uma discussão \
com começo/meio/fim).
2. {n_shorts} SHORTS de {s_min} a {s_max} segundos — momentos com gancho forte nos \
primeiros 3 segundos, autocontidos, com pico de humor, polêmica, emoção ou insight.

Regras obrigatórias:
- Use APENAS timestamps que existem na transcrição.
- O corte deve começar no início de uma fala e terminar no fim de uma ideia.
- NUNCA tire uma fala de contexto de forma que distorça o que a pessoa disse.
- Títulos chamativos mas fiéis ao conteúdo (sem clickbait mentiroso), em português.
- Descrição: 2-3 frases + créditos ao podcast original + hashtags relevantes.
- thumb_text: frase de impacto de no máximo 6 palavras para a thumbnail.

Responda SOMENTE com JSON válido neste formato:
{{
  "long": [
    {{"start_ts": "HH:MM:SS", "end_ts": "HH:MM:SS", "title": "...", "description": "...",
      "hashtags": ["#..."], "thumb_text": "...", "score": 0.0}}
  ],
  "shorts": [
    {{"start_ts": "HH:MM:SS", "end_ts": "HH:MM:SS", "title": "...", "description": "...",
      "hashtags": ["#..."], "thumb_text": "...", "score": 0.0}}
  ]
}}

TRANSCRIÇÃO:
{transcript}
"""


def _ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _parse_ts(ts: str) -> float:
    parts = [int(p) for p in ts.strip().split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _snap(t: float, boundaries: list[float]) -> float:
    """Ajusta t para o limite de segmento mais próximo (corte limpo)."""
    return min(boundaries, key=lambda b: abs(b - t)) if boundaries else t


def find_highlights(
    transcript: dict,
    video_title: str,
    video_url: str,
    log: Callable[[str], None] = print,
) -> dict:
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("AVISO: ANTHROPIC_API_KEY não definida — gerando cortes MOCK para teste")
        return _mock_cuts(transcript, video_url)

    lines = [f"[{_ts(s['start'])}] {s['text']}" for s in transcript["segments"]]
    prompt = PROMPT.format(
        video_title=video_title,
        podcast=CONFIG["podcast"]["nome"] or "podcast original",
        duration_min=duration / 60,
        n_long=cuts_cfg["long"]["count"],
        long_min=cuts_cfg["long"]["min_minutes"],
        long_max=cuts_cfg["long"]["max_minutes"],
        n_shorts=cuts_cfg["shorts"]["count"],
        s_min=cuts_cfg["shorts"]["min_seconds"],
        s_max=cuts_cfg["shorts"]["max_seconds"],
        transcript="\n".join(lines),
    )

    import anthropic

    client = anthropic.Anthropic()
    log(f"Consultando {CONFIG['llm']['model']} para selecionar os cortes…")
    resp = client.messages.create(
        model=CONFIG["llm"]["model"],
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    data = _extract_json(raw)

    starts = [s["start"] for s in transcript["segments"]]
    ends = [s["end"] for s in transcript["segments"]]
    result = {"long": [], "shorts": [], "mock": False}
    for kind in ("long", "shorts"):
        for item in data.get(kind, []):
            start = _snap(_parse_ts(item["start_ts"]), starts)
            end = _snap(_parse_ts(item["end_ts"]), ends)
            if end <= start or end > duration + 5:
                continue
            result[kind].append(
                {
                    "start": start,
                    "end": min(end, duration),
                    "title": item.get("title", "Corte"),
                    "description": _with_credits(item, video_url),
                    "hashtags": item.get("hashtags", []),
                    "thumb_text": item.get("thumb_text", ""),
                    "score": item.get("score", 0),
                }
            )
        result[kind].sort(key=lambda c: -c["score"])
    log(f"Selecionados: {len(result['long'])} cortes longos, {len(result['shorts'])} shorts")
    return result


def _with_credits(item: dict, video_url: str) -> str:
    desc = item.get("description", "").strip()
    podcast = CONFIG["podcast"]["nome"]
    credits = f"\n\n🎙️ Episódio completo: {video_url}"
    if podcast:
        credits = f"\n\n🎙️ Corte do podcast {podcast}.\nEpisódio completo: {video_url}"
    tags = " ".join(item.get("hashtags", []))
    return f"{desc}{credits}\n\n{tags}".strip()


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"LLM não retornou JSON: {text[:200]}")
    return json.loads(match.group())


def _mock_cuts(transcript: dict, video_url: str) -> dict:
    """Janelas uniformes só para validar download/edição/legenda sem API key."""
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]
    result = {"long": [], "shorts": [], "mock": True}

    long_len = cuts_cfg["long"]["min_minutes"] * 60
    for i in range(cuts_cfg["long"]["count"]):
        start = (i + 1) * duration / (cuts_cfg["long"]["count"] + 2)
        if start + long_len > duration:
            break
        result["long"].append(
            {
                "start": start,
                "end": start + long_len,
                "title": f"[MOCK] Corte longo {i + 1}",
                "description": f"Corte de teste (sem API key).\n\nEpisódio: {video_url}",
                "hashtags": ["#podcast"],
                "thumb_text": f"CORTE {i + 1}",
                "score": 0,
            }
        )
    short_len = cuts_cfg["shorts"]["max_seconds"]
    for i in range(cuts_cfg["shorts"]["count"]):
        start = (i + 1) * duration / (cuts_cfg["shorts"]["count"] + 2)
        if start + short_len > duration:
            break
        result["shorts"].append(
            {
                "start": start,
                "end": start + short_len,
                "title": f"[MOCK] Short {i + 1}",
                "description": f"Short de teste (sem API key).\n\nEpisódio: {video_url}",
                "hashtags": ["#shorts"],
                "thumb_text": f"SHORT {i + 1}",
                "score": 0,
            }
        )
    return result
