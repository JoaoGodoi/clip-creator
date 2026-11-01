"""Carrega config.yaml e localiza binários externos (ffmpeg)."""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()


def path_for(key: str) -> Path:
    p = ROOT / CONFIG["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def ollama_url() -> str:
    """URL do Ollama. `localhost` vira 127.0.0.1: no Windows ele tenta IPv6 (::1)
    primeiro, o Ollama só escuta IPv4 e a tentativa gasta ~2s antes de cair pro IPv4.
    Instalado pelo .exe, o run.bat aponta PODCAST_OLLAMA_URL pro Ollama da pasta do app."""
    url = (os.environ.get("PODCAST_OLLAMA_URL")
           or CONFIG["llm"].get("ollama_url", "http://127.0.0.1:11434")).rstrip("/")
    return url.replace("//localhost:", "//127.0.0.1:")


def ytdlp_auth() -> dict:
    """Login do YouTube para o yt-dlp, quando ele começa a pedir "Sign in to confirm
    you're not a bot" (IP marcado por muitos downloads). Opcional:
    - cookies.txt na pasta do app (exportado do navegador logado), ou
    - youtube.cookies_from_browser no config.yaml (firefox funciona; chrome/edge
      no Windows criptografam os cookies e o yt-dlp não consegue ler)."""
    cookie_file = ROOT / "cookies.txt"
    if cookie_file.exists():
        return {"cookiefile": str(cookie_file)}
    browser = (CONFIG.get("youtube") or {}).get("cookies_from_browser")
    if browser:
        return {"cookiesfrombrowser": (str(browser).lower(),)}
    return {}


def find_ffmpeg() -> str | None:
    """Procura ffmpeg no PATH, na pasta do instalador e nos locais padrão do winget."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = glob.glob(str(ROOT.parent / "tools" / "ffmpeg" / "ffmpeg.exe"))
    candidates += glob.glob(
        os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe"
        ),
        recursive=True,
    )
    candidates += glob.glob(r"C:\ffmpeg\bin\ffmpeg.exe")
    return candidates[0] if candidates else None


FFMPEG = find_ffmpeg()


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
