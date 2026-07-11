"""API local do Podcast Clipper. Rode com: uvicorn api:app --port 8765"""
from __future__ import annotations

import os
import shutil
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
    dopamine: bool = False


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
    dopamine_dir = ROOT / CONFIG["paths"]["assets"] / "dopamine"
    return {
        "ffmpeg": bool(FFMPEG),
        "llm_ok": llm_ok,
        "llm_detail": llm_detail,
        "intro": (ROOT / CONFIG["paths"]["assets"] / "intro.mp4").exists(),
        "outro": (ROOT / CONFIG["paths"]["assets"] / "outro.mp4").exists(),
        "whisper_model": CONFIG["whisper"]["model"],
        "dopamine_videos": len(list(dopamine_dir.glob("*.mp4"))) if dopamine_dir.exists() else 0,
    }


# ── Arquivos gerados (listar/apagar) ─────────────────────────────────────────

def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


@app.get("/api/storage")
def storage() -> dict:
    items = []
    downloads = path_for("downloads")
    for f in sorted(downloads.glob("*.mp4")):
        size = f.stat().st_size
        items.append({
            "type": "download", "name": f.name, "path": str(f),
            "size_mb": round(size / 1e6, 1),
        })
    for d in sorted(path_for("output").iterdir()):
        if d.is_dir():
            items.append({
                "type": "output", "name": d.name, "path": str(d),
                "size_mb": round(_dir_size(d) / 1e6, 1),
            })
    return {"items": items, "total_mb": round(sum(i["size_mb"] for i in items), 1)}


def _safe_target(raw: str) -> Path:
    target = Path(raw).resolve()
    roots = [path_for("downloads").resolve(), path_for("output").resolve()]
    if not any(target != root and target.is_relative_to(root) for root in roots):
        raise HTTPException(400, "Caminho fora das pastas do app")
    if not target.exists():
        raise HTTPException(404, "Arquivo não existe")
    return target


@app.post("/api/delete")
def delete_item(req: ChannelReq) -> dict:
    target = _safe_target(req.url)
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except PermissionError:
        raise HTTPException(
            409, f"'{target.name}' está em uso — feche o vídeo/player e tente de novo"
        )
    return {"ok": True}


@app.post("/api/delete_all")
def delete_all() -> dict:
    """Apaga todos os vídeos baixados e todos os cortes gerados (mantém transcrições)."""
    errors: list[str] = []
    targets = list(path_for("downloads").glob("*.mp4"))
    targets += [d for d in path_for("output").iterdir() if d.is_dir()]
    for t in targets:
        try:
            shutil.rmtree(t) if t.is_dir() else t.unlink()
        except PermissionError:
            errors.append(f"{t.name} (em uso)")
    return {"ok": not errors, "errors": errors}


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
    return {"job_id": jobs.start_job(req.url, req.title, dopamine=req.dopamine)}


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
