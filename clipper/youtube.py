"""Chamadas ao yt-dlp com login automático quando o YouTube pede ("not a bot").

Quando muito download sai do mesmo IP, o YouTube passa a responder "Sign in to
confirm you're not a bot". Aí tentamos de novo com o login do Firefox, se houver,
sem a pessoa precisar configurar nada. Chrome/Edge não servem: no Windows eles
criptografam os cookies de um jeito que o yt-dlp não consegue ler.
"""
from __future__ import annotations

import os
from pathlib import Path

import yt_dlp

from .config import ytdlp_auth

BOT_CHECK = "confirm you"  # "Sign in to confirm you're not a bot"

NO_FIREFOX = (
    "O YouTube bloqueou o download e está pedindo login (\"confirme que não é um robô\").\n"
    "Para resolver: instale o Firefox, entre no youtube.com com uma conta (de preferência "
    "uma secundária), feche o Firefox e tente de novo. O app usa esse login sozinho.\n"
    "Às vezes só reiniciar o modem/roteador ou desligar a VPN já resolve."
)
STILL_BLOCKED = (
    "O YouTube continua pedindo login, mesmo usando o login do navegador.\n"
    "Abra o Firefox, entre no youtube.com com uma conta (de preferência uma secundária), "
    "feche o Firefox e tente de novo. Se continuar, reinicie o modem/roteador."
)


class YouTubeBlocked(RuntimeError):
    """O YouTube pediu login; a mensagem já diz em português o que fazer."""


# Depois que o Firefox resolveu uma vez, usa direto (não esbarra no bloqueio a cada vídeo)
_use_firefox = False


def _firefox_has_profile() -> bool:
    profiles = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    return any(profiles.glob("*/cookies.sqlite"))


def _run(opts: dict, url: str, download: bool) -> dict:
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=download)


def extract(opts: dict, url: str, download: bool) -> dict:
    """ydl.extract_info com o login configurado (cookies.txt / config.yaml) ou,
    se o YouTube pedir, com o login do Firefox."""
    global _use_firefox
    auth = ytdlp_auth()
    if not auth and _use_firefox:
        auth = {"cookiesfrombrowser": ("firefox",)}
    try:
        return _run({**opts, **auth}, url, download)
    except yt_dlp.utils.DownloadError as e:
        if BOT_CHECK not in str(e):
            raise
        if auth:
            raise YouTubeBlocked(STILL_BLOCKED) from e
        if not _firefox_has_profile():
            raise YouTubeBlocked(NO_FIREFOX) from e

    try:
        info = _run({**opts, "cookiesfrombrowser": ("firefox",)}, url, download)
    except yt_dlp.utils.DownloadError as e:
        if BOT_CHECK in str(e):
            raise YouTubeBlocked(STILL_BLOCKED) from e
        raise
    _use_firefox = True
    return info
