"""Orquestrador: roda o pipeline completo em background e expõe o progresso."""
from __future__ import annotations

import json
import random
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import captions, downloader, editor, highlights, thumbnails, transcriber
from .config import CONFIG, ROOT, path_for


@dataclass
class Job:
    id: str
    video_url: str
    video_title: str
    status: str = "na fila"          # na fila | rodando | concluído | erro
    stage: str = ""
    progress: float = 0.0
    log: list[str] = field(default_factory=list)
    results: dict = field(default_factory=lambda: {"long": [], "shorts": []})
    error: str = ""
    mock: bool = False
    dopamine: bool = False
    cuts_mode: str = "both"          # both | shorts | long
    shorts_seconds: tuple[int, int] | None = None  # (mín, máx) escolhido na tela; None = config.yaml
    output_dir: str = ""

    def add_log(self, msg: str) -> None:
        self.log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "video_url": self.video_url, "video_title": self.video_title,
            "status": self.status, "stage": self.stage, "progress": round(self.progress, 1),
            "log": self.log[-60:], "results": self.results, "error": self.error,
            "mock": self.mock, "output_dir": self.output_dir,
        }


JOBS: dict[str, Job] = {}

# A GPU só aguenta um Whisper por vez — jobs simultâneos revezam a transcrição
# enquanto as demais etapas (download, LLM, render) rodam em paralelo.
_GPU_LOCK = threading.Lock()


def start_job(video_url: str, video_title: str, dopamine: bool = False,
              cuts_mode: str = "both", shorts_seconds: tuple[int, int] | None = None) -> str:
    job = Job(id=uuid.uuid4().hex[:8], video_url=video_url, video_title=video_title,
              dopamine=dopamine, cuts_mode=cuts_mode, shorts_seconds=shorts_seconds)
    JOBS[job.id] = job
    threading.Thread(target=_pipeline, args=(job,), daemon=True).start()
    return job.id


def _safe(name: str, maxlen: int = 60) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r]+', "", name).strip()
    return name[:maxlen].strip() or "sem_titulo"


def _set(job: Job, stage: str, progress: float) -> None:
    job.stage = stage
    job.progress = progress


def _pipeline(job: Job) -> None:
    job.status = "rodando"
    try:
        downloads = path_for("downloads")

        # 1. Download (com cache)
        _set(job, "Baixando vídeo", 1)
        job.add_log(f"Iniciando: {job.video_title}")
        video_id = job.video_url.split("v=")[-1]
        cached = downloads / f"{video_id}.mp4"
        if cached.exists():
            src = cached
            job.add_log("Vídeo já baixado, usando cache")
        else:
            src = downloader.download(
                job.video_url, downloads,
                progress_cb=lambda p, _: _set(job, "Baixando vídeo", 1 + p * 19),
            )
            job.add_log(f"Download concluído: {src.name}")
        _set(job, "Baixando vídeo", 20)

        # 2. Transcrição (com cache)
        transcript_cache = downloads / f"{video_id}.transcript.json"
        if transcript_cache.exists():
            transcript = json.loads(transcript_cache.read_text(encoding="utf-8"))
            job.add_log("Transcrição em cache, reutilizando")
        else:
            _set(job, "Aguardando GPU para transcrever", 21)
            with _GPU_LOCK:
                _set(job, "Transcrevendo (Whisper)", 21)
                wcfg = CONFIG["whisper"]
                transcript = transcriber.transcribe(
                    src, wcfg["model"], wcfg["language"],
                    log=job.add_log,
                    progress_cb=lambda p: _set(job, "Transcrevendo (Whisper)", 21 + p * 29),
                )
            transcript_cache.write_text(
                json.dumps(transcript, ensure_ascii=False), encoding="utf-8"
            )
            job.add_log(f"Transcrição pronta: {len(transcript['segments'])} falas")
        _set(job, "Transcrevendo (Whisper)", 50)

        # 3. Seleção de cortes
        _set(job, "Escolhendo os melhores cortes", 52)
        cuts = highlights.find_highlights(
            transcript, job.video_title, job.video_url,
            log=job.add_log, cuts_mode=job.cuts_mode, shorts_seconds=job.shorts_seconds,
        )
        job.mock = cuts.get("mock", False)

        # 4. Renderização (paralela)
        out_root = path_for("output") / f"{_safe(job.video_title)}_{video_id}"
        job.output_dir = str(out_root)
        tasks = [("long", i, cut) for i, cut in enumerate(cuts["long"], 1)]
        tasks += [("shorts", i, cut) for i, cut in enumerate(cuts["shorts"], 1)]
        total = len(tasks) or 1
        done = 0
        workers = max(1, CONFIG["render"].get("parallel_renders", 3))
        _set(job, f"Renderizando {total} corte(s) ({workers} em paralelo)", 55)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            renderers = {"long": _render_long, "shorts": _render_short}
            futures = {
                pool.submit(renderers[kind], job, src, out_root, i, cut, transcript): kind
                for kind, i, cut in tasks
            }
            for fut in as_completed(futures):
                job.results[futures[fut]].append(fut.result())
                done += 1
                _set(job, f"Renderizando cortes ({done}/{total})", 55 + done / total * 40)

        _set(job, "Concluído", 100)
        job.status = "concluído"
        job.add_log(f"Tudo pronto em: {out_root}")
    except Exception as e:  # noqa: BLE001 — erro vai para a UI
        job.status = "erro"
        job.error = f"{type(e).__name__}: {e}"
        job.add_log(f"ERRO: {job.error}")
        job.add_log(traceback.format_exc().splitlines()[-2])


def _clip_meta(cut: dict, folder: Path, files: dict) -> dict:
    meta = {
        "title": cut["title"], "description": cut["description"],
        "hashtags": cut["hashtags"], "seo_tags": cut.get("seo_tags", []),
        "start": cut["start"], "end": cut["end"],
        "duration": round(cut["end"] - cut["start"], 1), "folder": str(folder), **files,
    }
    (folder / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "descricao.txt").write_text(
        f"{cut['title']}\n\n{cut['description']}", encoding="utf-8"
    )
    return meta


def _rel(p: Path) -> str:
    return str(p.relative_to(path_for("output"))).replace("\\", "/")


def _render_long(job: Job, src: Path, out_root: Path, i: int, cut: dict, transcript: dict) -> dict:
    folder = out_root / "longos" / f"{i:02d} - {_safe(cut['title'])}"
    folder.mkdir(parents=True, exist_ok=True)

    clip = editor.render_long(src, cut["start"], cut["end"], folder / "video.mp4")
    job.add_log(f"Corte longo {i} renderizado ({(cut['end'] - cut['start']) / 60:.1f} min)")

    frame = editor.extract_frame(src, (cut["start"] + cut["end"]) / 2, folder / "_frame.jpg")
    thumbnails.make_thumbnail(frame, cut.get("thumb_text", ""), folder / "thumbnail.jpg")
    frame.unlink(missing_ok=True)

    return _clip_meta(cut, folder, {
        "video": _rel(clip), "thumbnail": _rel(folder / "thumbnail.jpg"), "kind": "long",
    })


def _pick_asset(folder: str) -> Path | None:
    base = ROOT / CONFIG["paths"]["assets"] / folder
    videos = list(base.glob("*.mp4")) + list(base.glob("*.gif"))
    return random.choice(videos) if videos else None


def _render_short(job: Job, src: Path, out_root: Path, i: int, cut: dict, transcript: dict) -> dict:
    folder = out_root / "shorts" / f"{i:02d} - {_safe(cut['title'])}"
    folder.mkdir(parents=True, exist_ok=True)

    bg = overlay = None
    if job.dopamine:
        bg = _pick_asset("dopamine")
        if not bg:
            job.add_log("Modo dopamina ligado, mas assets/dopamine/ está vazio — shorts normais")
    if not bg:
        overlay = _pick_asset("overlay")

    ass = captions.build_ass(
        transcript["words"], cut["start"], cut["end"], folder / "legenda.ass",
        margin_v=820 if bg else 620,
        hook_text=cut.get("thumb_text", ""),
    )
    clip = editor.render_short(
        src, cut["start"], cut["end"], ass, folder / "video.mp4", bg=bg, overlay=overlay
    )
    extra = f" + gameplay {bg.stem}" if bg else (f" + fundo {overlay.stem}" if overlay else "")
    job.add_log(f"Short {i} renderizado ({cut['end'] - cut['start']:.0f}s){extra}")

    return _clip_meta(cut, folder, {"video": _rel(clip), "kind": "short"})
