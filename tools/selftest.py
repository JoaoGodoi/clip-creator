"""Teste rápido da instalação (o setup.bat roda no final).

Exercita de verdade as partes que já quebraram por versão de biblioteca:
decodificar áudio com o faster-whisper (PyAV) e o solver JS do yt-dlp.
Sai com código 1 se algo essencial falhar.

Rodar:  .venv\\Scripts\\python.exe tools\\selftest.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

failed = False


def check(name: str, fn) -> None:
    global failed
    try:
        detail = fn()
        print(f"    OK: {name}" + (f" ({detail})" if detail else ""))
    except Exception as e:  # noqa: BLE001 — o teste só reporta
        failed = True
        print(f"    FALHOU: {name}: {type(e).__name__}: {e}")


def _imports() -> str:
    import anthropic, fastapi, googleapiclient, PIL, uvicorn, yaml  # noqa: F401,E401
    return ""


def _ffmpeg() -> str:
    from clipper.config import FFMPEG
    if not FFMPEG:
        raise RuntimeError("ffmpeg não encontrado")
    return FFMPEG


def _decode_audio() -> str:
    import av
    from faster_whisper.audio import decode_audio
    from clipper.config import FFMPEG

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "tom.wav"
        subprocess.run(
            [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=d=1", "-ar", "16000", str(wav)],
            check=True,
        )
        samples = decode_audio(str(wav))
    if len(samples) < 8000:
        raise RuntimeError(f"áudio decodificado curto demais ({len(samples)} amostras)")
    return f"av {av.__version__}"


def _ytdlp() -> str:
    import yt_dlp
    import yt_dlp_ejs  # noqa: F401 — sem ele o YouTube devolve 403
    return f"yt-dlp {yt_dlp.version.__version__}"


def _gpu() -> str:
    import ctranslate2
    n = ctranslate2.get_cuda_device_count()
    return f"{n} GPU(s) CUDA" if n else "sem GPU CUDA, transcrição na CPU"


check("bibliotecas", _imports)
check("ffmpeg", _ffmpeg)
check("decodificar áudio (faster-whisper/PyAV)", _decode_audio)
check("yt-dlp + solver do YouTube", _ytdlp)
check("aceleração", _gpu)

sys.exit(1 if failed else 0)
