"""Listagem de vídeos de um canal do YouTube via yt-dlp (sem API key)."""
from __future__ import annotations

import yt_dlp


def _normalize(url: str) -> str:
    url = url.strip().rstrip("/")
    is_channel = any(m in url for m in ("/@", "/channel/", "/c/", "/user/"))
    tail = url.rsplit("/", 1)[-1]
    if is_channel and tail not in ("videos", "streams", "shorts"):
        url += "/videos"
    return url


def list_videos(channel_url: str, limit: int = 24) -> list[dict]:
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "playlist_items": f"1:{limit}",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(_normalize(channel_url), download=False)

    entries = info.get("entries") or []
    videos = []
    for e in entries:
        if not e or not e.get("id"):
            continue
        if e.get("availability") in ("subscriber_only", "premium_only", "needs_auth"):
            continue
        dur = e.get("duration") or 0
        videos.append(
            {
                "id": e["id"],
                "url": f"https://www.youtube.com/watch?v={e['id']}",
                "title": e.get("title") or e["id"],
                "duration": dur,
                "duration_str": _fmt(dur),
                "thumbnail": f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg",
            }
        )
    return videos


def _fmt(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
