"""Download de vídeos via yt-dlp."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import youtube
from .config import FFMPEG


def download(video_url: str, dest_dir: Path, progress_cb: Callable[[float, str], None] | None = None) -> Path:
    """Baixa o vídeo em até 1080p mp4. Retorna o caminho do arquivo."""
    result: dict = {}

    def hook(d: dict) -> None:
        if d["status"] == "downloading" and progress_cb:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                progress_cb(d.get("downloaded_bytes", 0) / total, "baixando")
        elif d["status"] == "finished":
            result["path"] = d.get("filename")

    opts = {
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "noplaylist": True,
    }
    if FFMPEG:
        opts["ffmpeg_location"] = str(Path(FFMPEG).parent)

    info = youtube.extract(opts, video_url, download=True)

    final = dest_dir / f"{info['id']}.mp4"
    if final.exists():
        return final
    if result.get("path"):
        return Path(result["path"])
    raise FileNotFoundError(f"Download terminou mas o arquivo não foi encontrado em {dest_dir}")
