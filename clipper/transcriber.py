"""Transcrição com faster-whisper, com timestamps por palavra.

Tenta GPU (CUDA/float16) e cai para CPU (int8) se as libs NVIDIA não estiverem
disponíveis. As DLLs de cuBLAS/cuDNN instaladas via pip são adicionadas ao
search path em tempo de execução.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable


def _register_nvidia_dlls() -> None:
    try:
        import nvidia  # type: ignore
    except ImportError:
        return
    for base in nvidia.__path__:
        for sub in Path(base).glob("*/bin"):
            try:
                os.add_dll_directory(str(sub))
                os.environ["PATH"] = str(sub) + os.pathsep + os.environ["PATH"]
            except OSError:
                pass


_MODEL = None
_MODEL_SIZE = None


def _get_model(model_size: str, log: Callable[[str], None]):
    """Mantém o modelo carregado entre jobs (economiza ~30s por vídeo)."""
    global _MODEL, _MODEL_SIZE
    if _MODEL is not None and _MODEL_SIZE == model_size:
        return _MODEL

    from faster_whisper import WhisperModel

    _register_nvidia_dlls()
    try:
        _MODEL = WhisperModel(model_size, device="cuda", compute_type="float16")
        log(f"Whisper '{model_size}' carregado na GPU")
    except Exception as e:  # noqa: BLE001 — qualquer falha de CUDA cai para CPU
        log(f"GPU indisponível ({type(e).__name__}), usando CPU (mais lento)")
        _MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
    _MODEL_SIZE = model_size
    return _MODEL


def transcribe(
    media_path: Path,
    model_size: str = "medium",
    language: str = "pt",
    log: Callable[[str], None] = print,
    progress_cb: Callable[[float], None] | None = None,
) -> dict:
    """Retorna {"segments": [...], "words": [...], "duration": float}."""
    model = _get_model(model_size, log)

    seg_iter, info = model.transcribe(
        str(media_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    segments: list[dict] = []
    words: list[dict] = []
    duration = info.duration or 0.0
    for seg in seg_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        for w in seg.words or []:
            words.append({"start": w.start, "end": w.end, "word": w.word.strip()})
        if progress_cb and duration:
            progress_cb(min(seg.end / duration, 1.0))

    return {"segments": segments, "words": words, "duration": duration}
