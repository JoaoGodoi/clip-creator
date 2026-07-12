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
import unicodedata
from typing import Callable

import requests

from .config import CONFIG, ROOT

RULES = """Regras obrigatórias:
- Use APENAS timestamps que existem na transcrição.
- O corte deve começar no início de uma fala e terminar no fim de uma ideia.
- Marque o TRECHO COMPLETO do momento (contexto + clímax + desfecho), NUNCA apenas \
a frase de impacto. Respeite a duração mínima pedida — cortes curtos demais são descartados.
- NUNCA tire uma fala de contexto de forma que distorça o que a pessoa disse.
- NÃO escolha: agradecimentos, recados e publicidade, apresentação de convidado, \
transições ("agora vamos falar de..."), conversa administrativa do programa, meio de \
explicação sem conclusão, nem trechos que só fazem sentido com contexto anterior.
- hook_quote: copie EXATAMENTE as primeiras palavras faladas do corte (6 a 15 palavras), \
letra por letra como aparecem na transcrição. Corte cujo hook_quote não existir na \
transcrição será descartado automaticamente.
- title: fórmula de gancho em até 60 caracteres — pergunta direta, afirmação polêmica, \
"Fulano revela...", número ("3 erros que..."). Inclua o NOME da pessoa que fala se for \
identificável. Fiel ao conteúdo (sem clickbait mentiroso), em português.
- description: a PRIMEIRA linha repete o gancho com palavras-chave de busca (nome do \
convidado + tema); depois 1-2 frases sobre o trecho. Em português.
- hashtags: EXATAMENTE 3 a 5 — "#shorts" primeiro (em shorts), depois 1-2 amplas do \
nicho (ex: #podcast, #cortes) e 1-2 específicas do tema/convidado.
- seo_tags: 8 a 12 palavras-chave de busca (sem #), da mais específica à mais ampla: \
nome de quem fala, tema exato, assunto geral, nome do podcast, variações que alguém digitaria.
- thumb_text: frase de impacto de no máximo 6 palavras (vira headline na tela e thumbnail).
- score: 0 a 10. Seja rigoroso — 8+ só para momentos realmente fortes.
- QUALIDADE acima de quantidade: se o trecho for morno, retorne menos candidatos ou nenhum."""

ITEM_FMT = """{{"start_ts": "HH:MM:SS", "end_ts": "HH:MM:SS", "hook_quote": "...",
  "title": "...", "description": "...", "hashtags": ["#..."], "seo_tags": ["..."],
  "thumb_text": "...", "score": 0.0}}"""

PROMPT_JUDGE = """Você é o editor-chefe de um canal de cortes de podcast. Abaixo está a \
lista de cortes CANDIDATOS que sua equipe propôs para o episódio "{video_title}" do \
podcast {podcast}.

Sua tarefa: escolher APENAS os melhores, comparando-os entre si. Seja implacável — \
postar corte fraco afunda o canal.

O que faz um corte forte:
- Gancho: a primeira frase prende em 3 segundos (pergunta forte, polêmica, começo de \
história, punchline chegando).
- Autocontido: entende-se sem ter visto o resto do episódio.
- Pico real: humor, tensão, revelação ou insight — NÃO conversa administrativa, \
agradecimento, divagação ou explicação morna.

Selecione no máximo {n_shorts} shorts e {n_long} cortes longos. Candidato fraco não \
entra — poucos cortes bons valem mais que muitos medianos. Dê a nota final de 0 a 10 \
comparando os candidatos entre si; reserve 8+ para os realmente excepcionais.

Responda SOMENTE com JSON:
{{"selected": [{{"id": 0, "score": 0.0}}]}}

CANDIDATOS:
{candidates}
"""

PROMPT_FULL = """Você é um editor de cortes de podcast experiente. Abaixo está a transcrição \
de um episódio, com o timestamp de início de cada fala.

Título do episódio: {video_title}
Podcast: {podcast}
Duração total: {duration_min:.0f} minutos

Selecione:
{requests}

{rules}

Responda SOMENTE com JSON válido neste formato:
{{"long": [{item_fmt}], "shorts": [{item_fmt}]}}

TRANSCRIÇÃO:
{transcript}
"""

PROMPT_BLOCK = """Você é um editor de cortes de podcast experiente. Abaixo está um TRECHO \
(de {block_start} a {block_end}) da transcrição do episódio "{video_title}" do podcast {podcast}.

Liste os candidatos a corte que existem DENTRO deste trecho:
{requests}

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


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _locate_quote(quote: str, segments: list[dict], seg_norms: list[str]) -> float | None:
    """Acha o início da fala cujo texto contém a citação. None = citação inventada.

    O modelo é ruim de aritmética de timestamp mas bom de copiar texto — a
    citação de abertura vira a âncora real do corte.
    """
    q = _norm(quote)
    if len(q) < 8:
        return None
    for i in range(len(seg_norms)):
        joined = seg_norms[i]
        if q in joined:
            return segments[i]["start"]
        for j in (1, 2):
            if i + j >= len(seg_norms):
                break
            joined += " " + seg_norms[i + j]
            if q in joined:
                return segments[i]["start"]
    return None


def _excerpt(segments: list[dict], start: float, n_words: int = 40) -> str:
    words: list[str] = []
    for seg in segments:
        if seg["end"] <= start:
            continue
        words.extend(seg["text"].split())
        if len(words) >= n_words:
            break
    return " ".join(words[:n_words])


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


def _wants(cuts_mode: str, duration: float, log: Callable[[str], None]) -> tuple[bool, bool]:
    """(want_long, want_shorts) a partir do modo escolhido e da duração do vídeo."""
    want_shorts = cuts_mode != "long"
    want_long = cuts_mode != "shorts"
    if want_long:
        min_s = CONFIG["cuts"]["long"]["min_minutes"] * 60
        if duration < min_s:
            log(f"Vídeo curto ({duration / 60:.0f} min) — sem cortes longos")
            want_long = False
    return want_long, want_shorts


def _requests(want_long: bool, want_shorts: bool, per_block: bool) -> str:
    cuts_cfg = CONFIG["cuts"]
    lines: list[str] = []
    if want_shorts:
        s = cuts_cfg["shorts"]
        qty = "Até 3" if per_block else str(s["count"])
        lines.append(
            f"- {qty} SHORTS de {s['min_seconds']} a {s['max_seconds']} segundos — momentos "
            f"com gancho forte nos primeiros 3 segundos, autocontidos, com pico de humor, "
            f"polêmica, emoção ou insight."
        )
    else:
        lines.append('- NÃO gere shorts. Retorne "shorts": [].')
    if want_long:
        lo = cuts_cfg["long"]
        if per_block:
            lines.append(
                f"- Até 2 CORTES LONGOS de {lo['min_minutes']} a {lo['max_minutes']} minutos "
                f"— SOMENTE se este trecho contiver um bloco temático coeso completo "
                f"(história ou discussão com começo, meio e fim)."
            )
        else:
            lines.append(
                f"- {lo['count']} CORTES LONGOS de {lo['min_minutes']} a {lo['max_minutes']} "
                f"minutos — blocos temáticos coesos que funcionam como vídeo independente no "
                f"YouTube (uma história completa, uma discussão com começo/meio/fim)."
            )
    else:
        lines.append('- NÃO gere cortes longos. Retorne "long": [].')
    return "\n".join(lines)


# ── Entrada principal ────────────────────────────────────────────────────────

def find_highlights(
    transcript: dict,
    video_title: str,
    video_url: str,
    log: Callable[[str], None] = print,
    cuts_mode: str = "both",
) -> dict:
    want_long, want_shorts = _wants(cuts_mode, transcript["duration"], log)
    if not want_long and not want_shorts:
        return {"long": [], "shorts": [], "mock": False}
    provider = CONFIG["llm"].get("provider", "ollama")
    if provider == "ollama":
        return _ollama_highlights(transcript, video_title, video_url, log, want_long, want_shorts)
    return _anthropic_highlights(transcript, video_title, video_url, log, want_long, want_shorts)


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
                "think": bool(cfg.get("think", True)),
                "format": "json",
                "options": {"temperature": 0.3, "num_ctx": 16384},
            },
            timeout=900,
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


def _ollama_highlights(
    transcript: dict, video_title: str, video_url: str, log,
    want_long: bool, want_shorts: bool,
) -> dict:
    cfg = CONFIG["llm"]
    block_seconds = cfg.get("block_minutes", 20) * 60
    blocks = _blocks(transcript["segments"], block_seconds)
    log(f"Analisando transcrição em {len(blocks)} bloco(s) com {cfg['ollama_model']} (local)")

    candidates: dict[str, list[dict]] = {"long": [], "shorts": []}
    for i, block in enumerate(blocks, 1):
        lines = [f"[{_ts(s['start'])}] {s['text']}" for s in block]
        prompt = PROMPT_BLOCK.format(
            block_start=_ts(block[0]["start"]),
            block_end=_ts(block[-1]["end"]),
            video_title=video_title,
            podcast=CONFIG["podcast"]["nome"] or "podcast original",
            requests=_requests(want_long, want_shorts, per_block=True),
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

    candidates = _verify_anchors(candidates, transcript, log)
    candidates = _judge(candidates, transcript, video_title, log, want_long, want_shorts)
    return _rank_candidates(candidates, transcript, video_url, log, want_long, want_shorts)


def _verify_anchors(candidates: dict, transcript: dict, log) -> dict:
    """Descarta candidato cuja citação de abertura não existe na transcrição e
    ancora o início do corte no lugar real da citação."""
    segments = transcript["segments"]
    seg_norms = [_norm(s["text"]) for s in segments]
    verified: dict[str, list[dict]] = {"long": [], "shorts": []}
    dropped = 0
    for kind in ("long", "shorts"):
        for item in candidates[kind]:
            quote = str(item.get("hook_quote") or "").strip()
            if quote:
                loc = _locate_quote(quote, segments, seg_norms)
                if loc is None:
                    dropped += 1
                    continue
                try:
                    length = max(_parse_ts(item["end_ts"]) - _parse_ts(item["start_ts"]), 0)
                except (KeyError, ValueError):
                    length = 0
                item["start_ts"] = _ts(loc)
                item["end_ts"] = _ts(loc + length)
            verified[kind].append(item)
    if dropped:
        log(f"{dropped} candidato(s) descartado(s): citação de abertura não existe na transcrição")
    return verified


def _judge(candidates: dict, transcript: dict, video_title: str, log,
           want_long: bool, want_shorts: bool) -> dict:
    """Segunda chamada: o modelo compara TODOS os candidatos e escolhe os melhores.

    Nota de bloco não é calibrada entre blocos; julgamento comparativo é onde
    o modelo local acerta mais.
    """
    cuts_cfg = CONFIG["cuts"]
    n_long = cuts_cfg["long"]["count"] if want_long else 0
    n_shorts = cuts_cfg["shorts"]["count"] if want_shorts else 0
    min_score = float(cuts_cfg.get("min_score", 6))

    flat: list[tuple[str, dict]] = [(k, it) for k in ("long", "shorts") for it in candidates[k]]
    if len(flat) <= max(n_long + n_shorts, 1):
        return candidates  # nada para comparar

    segments = transcript["segments"]
    lines = []
    for idx, (kind, item) in enumerate(flat):
        try:
            start = _parse_ts(item.get("start_ts", "0"))
            length = max(_parse_ts(item.get("end_ts", "0")) - start, 0)
        except ValueError:
            start, length = 0.0, 0.0
        label = "CORTE LONGO" if kind == "long" else "SHORT"
        lines.append(
            f'[id {idx}] {label} ~{length:.0f}s — "{item.get("title", "?")}"\n'
            f'  gancho: "{item.get("hook_quote", "")}"\n'
            f'  trecho: "{_excerpt(segments, start)}…"'
        )

    prompt = PROMPT_JUDGE.format(
        video_title=video_title,
        podcast=CONFIG["podcast"]["nome"] or "podcast original",
        n_shorts=n_shorts,
        n_long=n_long,
        candidates="\n\n".join(lines),
    )
    try:
        data = _extract_json(_ollama_chat(prompt))
        selected = data["selected"]
        assert isinstance(selected, list)
    except Exception as e:  # noqa: BLE001 — juiz falhou: segue com os candidatos crus
        log(f"Etapa de juiz falhou ({e}) — usando notas dos blocos")
        return candidates

    result: dict[str, list[dict]] = {"long": [], "shorts": []}
    below = 0
    for sel in selected:
        try:
            kind, item = flat[int(sel["id"])]
            score = float(sel.get("score", 0))
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if score < min_score:
            below += 1
            continue
        item["score"] = score
        result[kind].append(item)
    skipped = len(flat) - len(selected)
    log(
        f"Juiz: {len(result['long']) + len(result['shorts'])} aprovado(s) de {len(flat)} "
        f"candidato(s) ({skipped} reprovados, {below} abaixo da nota mínima {min_score:g})"
    )
    return result


def _rank_candidates(
    candidates: dict, transcript: dict, video_url: str, log,
    want_long: bool = True, want_shorts: bool = True,
) -> dict:
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]
    starts = [s["start"] for s in transcript["segments"]]
    ends = [s["end"] for s in transcript["segments"]]

    limits = {
        "long": (cuts_cfg["long"]["min_minutes"] * 60,
                 cuts_cfg["long"]["max_minutes"] * 60,
                 cuts_cfg["long"]["count"] if want_long else 0),
        "shorts": (cuts_cfg["shorts"]["min_seconds"],
                   cuts_cfg["shorts"]["max_seconds"],
                   cuts_cfg["shorts"]["count"] if want_shorts else 0),
    }

    result = {"long": [], "shorts": [], "mock": False}
    for kind, (dur_min, dur_max, count) in limits.items():
        if count == 0:
            continue
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
                    "seo_tags": item.get("seo_tags") or [],
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

def _anthropic_highlights(
    transcript: dict, video_title: str, video_url: str, log,
    want_long: bool, want_shorts: bool,
) -> dict:
    duration = transcript["duration"]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("AVISO: ANTHROPIC_API_KEY não definida — gerando cortes MOCK para teste")
        return _mock_cuts(transcript, video_url, want_long, want_shorts)

    lines = [f"[{_ts(s['start'])}] {s['text']}" for s in transcript["segments"]]
    prompt = PROMPT_FULL.format(
        video_title=video_title,
        podcast=CONFIG["podcast"]["nome"] or "podcast original",
        duration_min=duration / 60,
        requests=_requests(want_long, want_shorts, per_block=False),
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
    candidates = _verify_anchors(
        {"long": data.get("long") or [], "shorts": data.get("shorts") or []},
        transcript, log,
    )
    return _rank_candidates(candidates, transcript, video_url, log, want_long, want_shorts)


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


def _mock_cuts(transcript: dict, video_url: str, want_long: bool = True, want_shorts: bool = True) -> dict:
    """Janelas uniformes só para validar download/edição/legenda sem LLM."""
    cuts_cfg = CONFIG["cuts"]
    duration = transcript["duration"]
    result = {"long": [], "shorts": [], "mock": True}

    long_len = cuts_cfg["long"]["min_minutes"] * 60
    for i in range(cuts_cfg["long"]["count"] if want_long else 0):
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
    for i in range(cuts_cfg["shorts"]["count"] if want_shorts else 0):
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
