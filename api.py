"""API local do Podcast Clipper. Rode com: uvicorn api:app --port 8765"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from clipper import channel, jobs
from clipper.config import CONFIG, FFMPEG, ROOT, has_api_key, path_for

app = FastAPI(title="Podcast Clipper")


class ChannelReq(BaseModel):
    url: str


class JobReq(BaseModel):
    url: str
    title: str


def _llm_status() -> tuple[bool, str]:
    cfg = CONFIG["llm"]
    provider = cfg.get("provider", "ollama")
    if provider == "anthropic":
        if has_api_key():
            return True, f"claude: {cfg.get('anthropic_model', '?')}"
        return False, "sem ANTHROPIC_API_KEY (modo mock)"

    import requests

    model = cfg.get("ollama_model", "?")
    try:
        resp = requests.get(f"{cfg.get('ollama_url', 'http://localhost:11434')}/api/tags", timeout=2)
        names = [m["name"] for m in resp.json().get("models", [])]
    except Exception:  # noqa: BLE001 — qualquer falha = ollama fora do ar
        return False, "ollama não está rodando"
    if any(n == model or n.startswith(model + ":") or n.split(":")[0] == model for n in names):
        return True, f"ollama: {model}"
    return False, f"modelo {model} não baixado (ollama pull {model})"


@app.get("/api/health")
def health() -> dict:
    llm_ok, llm_detail = _llm_status()
    return {
        "ffmpeg": bool(FFMPEG),
        "llm_ok": llm_ok,
        "llm_detail": llm_detail,
        "intro": (ROOT / CONFIG["paths"]["assets"] / "intro.mp4").exists(),
        "outro": (ROOT / CONFIG["paths"]["assets"] / "outro.mp4").exists(),
        "whisper_model": CONFIG["whisper"]["model"],
    }


@app.post("/api/channel")
def get_channel(req: ChannelReq) -> dict:
    try:
        return {"videos": channel.list_videos(req.url)}
    except Exception as e:  # noqa: BLE001 — erro de URL/rede vai para a UI
        raise HTTPException(400, f"Não consegui listar o canal: {e}")


@app.post("/api/jobs")
def create_job(req: JobReq) -> dict:
    if not FFMPEG:
        raise HTTPException(500, "ffmpeg não encontrado — instale e reinicie o app")
    return {"job_id": jobs.start_job(req.url, req.title)}


@app.get("/api/jobs")
def list_jobs() -> dict:
    ordered = sorted(jobs.JOBS.values(), key=lambda j: j.id)
    return {"jobs": [j.to_dict() for j in ordered]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return job.to_dict()


@app.post("/api/open")
def open_folder(req: ChannelReq) -> dict:
    """Abre a pasta no Explorer (só dentro de output/)."""
    target = Path(req.url).resolve()
    out_root = path_for("output").resolve()
    if not str(target).startswith(str(out_root)) or not target.exists():
        raise HTTPException(400, "Pasta inválida")
    subprocess.Popen(["explorer", str(target)])
    return {"ok": True}


app.mount("/files", StaticFiles(directory=path_for("output")), name="files")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
