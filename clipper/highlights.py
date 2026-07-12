"""Seleção dos melhores cortes sobre a transcrição.

Dois providers, escolhidos em config.yaml (llm.provider):
- ollama:    LLM local (grátis). A transcrição é analisada em blocos de
             ~20 min; cada bloco gera candidatos com nota e os melhores vencem.
- anthropic: Claude API (melhor qualidade, transcrição inteira de uma vez).
             Sem ANTHROPIC_API_KEY, cai em cortes "mock" só para testar o pipeline.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

import requests

from .config import CONFIG, ROOT

RULES = """Regras obrigatórias:
- Use APENAS timestamps que existem na transcrição.
- O corte deve começar no início de uma fala e terminar no fim de uma ideia.
- Marque o TRECHO COMPLETO do momento (contexto + clímax + desfecho), NUNCA apenas \
a frase de impacto. Respeite a duração mínima pedida — cortes curtos demais são descartados.
- NUNCA tire uma fala de contexto de forma que distorça o que a pessoa disse.
- Títulos chamativos mas fiéis ao conteúdo (sem clickbait mentiroso), em português.
- description: 2-3 frases sobre o trecho, em português.
- thumb_text: frase de impacto de no máximo 6 palavras para a thumbnail.
- score: 0 a 10. Seja rigoroso — 8+ só para momentos realmente fortes."""

ITEM_FMT = """{{"start_ts": "HH:MM:SS", "end_ts": "HH:MM:SS", "title": "...", "description": "...",
  "hashtags": ["#..."], "thumb_text": "...", "score": 0.0}}"""

PROMPT_FULL = """Você é um editor de cortes de podcast experiente. Abaixo está a transcrição \
de um episódio, com o timestamp de início de cada fala.

Título do episódio: {video_title}
Podcast: {podcast}
Duração total: {duration_min:.0f} minutos

Selecione:
{long_req}
2. {n_shorts} SHORTS de {s_min} a {s_max} segundos — momentos com gancho forte nos \
primeiros 3 segundos, autocontidos, com pico de humor, polêmica, emoção ou insight.

{rules}

Responda SOMENTE com JSON válido neste formato:
{{"long": [{item_fmt}], "shorts": [{item_fmt}]}}

TRANSCRIÇÃO:
{transcript}
"""

PROMPT_BLOCK = """Você é um editor de cortes de podcast experiente. Abaixo está um TRECHO \
(de {block_start} a {block_end}) da transcrição do episódio "{video_title}" do podcast {podcast}.

Liste os candidatos a corte que existem DENTRO deste trecho:
1. Até 3 SHORTS de {s_min} a {s_max} segundos — momentos com gancho forte nos primeiros \
3 segundos, autocontidos, com pico de humor, polêmica, emoção ou insight.
{long_req}

Se o trecho não tiver bons candidatos, retorne listas vazias — não invente.

{rules}

Responda SOMENTE com JSON válido neste formato:
{{"long": [{item_fmt}], "shorts": [{item_fmt}]}}

TRECHO DA TRANSCRIÇÃO:
{transcript}
"""


def _ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _parse_ts(ts: str) -> float:
    parts = [int(p) for p in str(ts).strip().split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _snap(t: float, boundaries: list[float]) -> float:
    """Ajusta t para o limite de segmento mais próximo (corte limpo)."""
    return min(boundaries, key=lambda b: abs(b - t)) if boundaries else t


def _fit_duration(
    start: float,
    end: float,
    segments: list[dict],
    dur_min: float,
    dur_max: float,
) -> tuple[float, float]:
    """Expande/encolhe o corte para caber em [dur_min, dur_max].

    LLMs (especialmente locais) tendem a marcar só a frase de impacto. O trecho
    marcado vira a âncora: estende para frente fala a fala até a duração alvo,
    preferindo parar em fim de frase; se faltar vídeo, estende para trás.
    """
    target = (dur_min + dur_max) / 2

    def ends_sentence(seg: dict) -> bool:
        return bool(seg["text"]) and seg["text"][-1] in ".!?…"

    if end - start < dur_min:
        for seg in segments:
            if seg["end"] <= end + 0.1:
                continue
            if seg["end"] - start > dur_max:
                break
            end = seg["end"]
            if end - start >= target or (end - start >= dur_min and ends_sentence(seg)):
                break
        if end - start < dur_min:
            for seg in reversed(segments):
                if seg["start"] >= start - 0.1:
                    continue
                if end - seg["start"] > dur_max:
                    break
                start = seg["start"]
                if end - start >= dur_min:
                    break

    if end - start > dur_max:
        best = start + dur_max
        for seg in reversed(segments):
            if start + 1 < seg["end"] <= start + dur_max:
                best = seg["end"]
                break
        end = best

    return start, end


def _wants_long(duration: float, log: Callable[[str], None]) -> bool:
    """Vídeo menor que o corte longo mínimo gera só shorts."""
    min_s = CONFIG["cuts"]["long"]["min_minutes"] * 60
    if duration < min_s:
        log(f"Vídeo curto ({duration / 60:.0f} min) — gerando apenas shorts")
        return False
    return True


def _long_req(want_long: bool, per_block: bool) -> str:
    cfg = CONFIG["cuts"]["long"]
    if not want_long:
        return 'NÃO sugira cortes longos — o vídeo é curto demais. Retorne "long": [].'
    if per_block:
        return (
            f"2. Até 2 CORTES LONGOS de {cfg['min_minutes']} a {cfg['max_minutes']} minutos "
            f"— SOMENTE se este trecho contiver um bloco temático coeso completo "
            f"(história ou discussão com começo, meio e fim)."
        )
    return (
        f"1. {cfg['count']} CORTES LONGOS de {cfg['min_minutes']} a {cfg['max_minutes']} "
        f"minutos — blocos temáticos coesos que funcionam como vídeo independente no "
        f"YouTube (uma história completa, uma discussão com começo/meio/fim)."
    )


# ── Entrada principal ────────────────────────────────────────────────────────

def find_highlights(
    transcript: dict,
    video_title: str,
    video_url: str,
    log: Callable[[str], None] = print,
) -> dict:
    provider = CONFIG["llm"].get("provider", "ollama")
    if provider == "ollama":
        return _ollama_highlights(transcript, video_title, video_url, log)
    return _anthropic_highlights(transcript, video_title, video_url, log)


# ── Provider: Ollama (local) ─────────────────────────────────────────────────

def _ollama_chat(prompt: str) -> str:
    cfg = CONFIG["llm"]
    url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
    try:
        resp = requests.post(
            f"{url}/api/chat",
            json={
                "model": cfg["ollama_model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "format": "json",
                "options": {"temperature": 0.4, "num_ctx": 16384},
            },
            timeout=600,
        )
    except requests.ConnectionError:
        raise RuntimeError(
            "Ollama não está rodando. Abra o app Ollama (ou rode 'ollama serve') e tente de novo."
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"Modelo '{cfg['ollama_model']}' não encontrado no Ollama. "
            f"Rode: ollama pull {cfg['ollama_model']}"
        )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _blocks(segments: list[dict], block_seconds: float) -> list[list[dict]]:
    blocks: list[list[dict]] = []
    current: list[dict] = []
    block_start = 0.0
    for seg in segments:
        if seg["start"] - block_start >= block_seconds and current:
            blocks.append(current)
            current = []
            block_start = seg["start"]
        current.append(seg)
    if current:
        blocks.append(current)
    return blocks


def _overlap_ratio(a: dict, b: dict) -> float:
    inter = min(a["end"], b["end"]) - max(a["start"], b["start"])
    shorter = min(a["end"] - a["start"], b["end"] - b["start"])
    return max(inter, 0) / shorter if shorter > 0 else 0


def _ollama_highlights(transcript: dict, video_title: str, video_url: str, log) -> dict:
    cfg = CONFIG["llm"]
    cuts_cfg = CONFIG["cuts"]
    block_seconds = cfg.get("block_minutes", 20) * 60
    blocks = _blocks(transcript["segments"], block_seconds)
    want_long = _wants_long(transcript["duration"], log)
    log(f"Analisando transcrição em {len(blocks)} bloco(s) com {cfg['ollama_model']} (local)")

    candidates: dict[str, list[dict]] = {"long": [], "shorts": []}
    for i, block in enumerate(blocks, 1):
        lines = [f"[{_ts(s['start'])}] {s['text']}" for s in block]
        prompt = PROMPT_BLOCK.format(
            block_start=_ts(block[0]["start"]),
            block_end=_ts(block[-1]["end"]),
            video_title=video_title,
            podcast=CONFIG["podcast"]["nome"] or "podcast original",
            s_min=cuts_cfg["shorts"]["min_seconds"],
            s_max=cuts_cfg["shorts"]["max_seconds"],
            long_req=_long_req(want_long, per_block=True),
            rules=RULES,
            item_fmt=ITEM_FMT,
            transcript="\n".join(lines),
        )
        try:
            data = _extract_json(_ollama_chat(prompt))
        except (ValueError, json.JSONDecodeError) as e:
            log(f"Bloco {i}/{len(blocks)}: resposta inválida do modelo, pulando ({e})")
            continue
        n = 0
        for kind in ("long", "shorts"):
            items = data.get(kind) or []
            candidates[kind].extend(items if isinstance(items, list) else [])
            n += len(items) if isinstance(items, list) else 0
        log(f"Bloco {i}/{len(blocks)} analisado: {n} candidato(s)")

    return _rank_candidates(candidates, transcript, video_url, log)


def _rank_candidates(candidates: dict, transcript: dict, video_url: str, log) -> dict:
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]
    starts = [s["start"] for s in transcript["segments"]]
    ends = [s["end"] for s in transcript["segments"]]

    limits = {
        "long": (cuts_cfg["long"]["min_minutes"] * 60,
                 cuts_cfg["long"]["max_minutes"] * 60,
                 cuts_cfg["long"]["count"]),
        "shorts": (cuts_cfg["shorts"]["min_seconds"],
                   cuts_cfg["shorts"]["max_seconds"],
                   cuts_cfg["shorts"]["count"]),
    }

    result = {"long": [], "shorts": [], "mock": False}
    for kind, (dur_min, dur_max, count) in limits.items():
        valid: list[dict] = []
        for item in candidates[kind]:
            try:
                start = _snap(_parse_ts(item["start_ts"]), starts)
                end = _snap(_parse_ts(item["end_ts"]), ends)
            except (KeyError, ValueError):
                continue
            if end <= start - 1 or start > duration:
                continue
            start, end = _fit_duration(
                start, max(end, start), transcript["segments"], dur_min, dur_max
            )
            length = end - start
            if length < dur_min * 0.8 or length > dur_max * 1.25 or end > duration + 5:
                continue
            valid.append(
                {
                    "start": start,
                    "end": min(end, duration),
                    "title": str(item.get("title") or "Corte").strip(),
                    "description": _with_credits(item, video_url),
                    "hashtags": item.get("hashtags") or [],
                    "thumb_text": str(item.get("thumb_text") or ""),
                    "score": float(item.get("score") or 0),
                }
            )
        valid.sort(key=lambda c: -c["score"])
        for cand in valid:
            if len(result[kind]) >= count:
                break
            if all(_overlap_ratio(cand, kept) < 0.3 for kept in result[kind]):
                result[kind].append(cand)

    music_credit = CONFIG.get("branding", {}).get("ending_music_credit", "")
    if music_credit and (ROOT / CONFIG["paths"]["assets"] / "outro.mp4").exists():
        for cut in result["long"]:
            cut["description"] += f"\n\n{music_credit}"

    log(f"Selecionados: {len(result['long'])} cortes longos, {len(result['shorts'])} shorts")
    return result


# ── Provider: Anthropic (Claude API) ─────────────────────────────────────────

def _anthropic_highlights(transcript: dict, video_title: str, video_url: str, log) -> dict:
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("AVISO: ANTHROPIC_API_KEY não definida — gerando cortes MOCK para teste")
        return _mock_cuts(transcript, video_url)

    lines = [f"[{_ts(s['start'])}] {s['text']}" for s in transcript["segments"]]
    prompt = PROMPT_FULL.format(
        video_title=video_title,
        podcast=CONFIG["podcast"]["nome"] or "podcast original",
        duration_min=duration / 60,
        long_req=_long_req(_wants_long(duration, log), per_block=False),
        n_shorts=cuts_cfg["shorts"]["count"],
        s_min=cuts_cfg["shorts"]["min_seconds"],
        s_max=cuts_cfg["shorts"]["max_seconds"],
        rules=RULES,
        item_fmt=ITEM_FMT,
        transcript="\n".join(lines),
    )

    import anthropic

    client = anthropic.Anthropic()
    model = CONFIG["llm"].get("anthropic_model", "claude-sonnet-5")
    log(f"Consultando {model} para selecionar os cortes…")
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _extract_json(resp.content[0].text)
    return _rank_candidates(
        {"long": data.get("long") or [], "shorts": data.get("shorts") or []},
        transcript, video_url, log,
    )


# ── Comum ────────────────────────────────────────────────────────────────────

def _with_credits(item: dict, video_url: str) -> str:
    desc = str(item.get("description") or "").strip()
    podcast = CONFIG["podcast"]["nome"]
    credits = f"\n\n🎙️ Episódio completo: {video_url}"
    if podcast:
        credits = f"\n\n🎙️ Corte do podcast {podcast}.\nEpisódio completo: {video_url}"
    tags = " ".join(item.get("hashtags") or [])
    return f"{desc}{credits}\n\n{tags}".strip()


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"LLM não retornou JSON: {text[:200]}")
    return json.loads(match.group())


def _mock_cuts(transcript: dict, video_url: str) -> dict:
    """Janelas uniformes só para validar download/edição/legenda sem LLM."""
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
                "description": f"Corte de teste (sem LLM).\n\nEpisódio: {video_url}",
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
                "description": f"Short de teste (sem LLM).\n\nEpisódio: {video_url}",
                "hashtags": ["#shorts"],
                "thumb_text": f"SHORT {i + 1}",
                "score": 0,
            }
        )
    return result
