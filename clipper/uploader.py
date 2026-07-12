"""Upload para o YouTube via Data API v3.

Fluxo: o usuário cria uma credencial OAuth "Desktop app" no Google Cloud
Console e salva como client_secret.json na raiz do projeto. O botão
"Conectar YouTube" na interface abre a tela de consentimento do Google;
o token fica em data/token.json e renova sozinho.

Nota: apps OAuth não verificados pelo Google têm uploads travados como
"privado" pelo YouTube — o vídeo sobe, você publica manualmente no Studio
(ou agenda) até o app passar pela verificação.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from .config import CONFIG, ROOT, path_for

CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN_FILE = ROOT / "data" / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_flow = None  # fluxo OAuth em andamento (single-user, local)


def has_client_secret() -> bool:
    return CLIENT_SECRET.exists()


def get_credentials():
    """Credenciais salvas, renovando se expiradas. None se nunca conectou."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds.valid else None


def auth_url(redirect_uri: str) -> str:
    """Gera a URL de consentimento do Google e guarda o fluxo para o callback."""
    global _flow
    from google_auth_oauthlib.flow import Flow

    if not has_client_secret():
        raise FileNotFoundError(
            "client_secret.json não encontrado na raiz do projeto — "
            "siga o GOOGLE_SETUP.md para criar a credencial"
        )
    _flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET), scopes=SCOPES, redirect_uri=redirect_uri
    )
    url, _ = _flow.authorization_url(access_type="offline", prompt="consent")
    return url


def finish_auth(code: str) -> None:
    """Troca o código do callback por credenciais e salva o token."""
    global _flow
    if _flow is None:
        raise RuntimeError("Nenhum fluxo de login em andamento — clique em Conectar de novo")
    _flow.fetch_token(code=code)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(_flow.credentials.to_json(), encoding="utf-8")
    _flow = None


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


def status() -> dict:
    if not has_client_secret():
        return {"configured": False, "connected": False, "channel": None}
    try:
        creds = get_credentials()
    except Exception:  # noqa: BLE001 — token corrompido/revogado = desconectado
        return {"configured": True, "connected": False, "channel": None}
    if not creds:
        return {"configured": True, "connected": False, "channel": None}

    from googleapiclient.discovery import build

    try:
        yt = build("youtube", "v3", credentials=creds)
        resp = yt.channels().list(part="snippet", mine=True).execute()
        channel = resp["items"][0]["snippet"]["title"] if resp.get("items") else "?"
    except Exception:  # noqa: BLE001 — sem rede/quota: conectado, canal desconhecido
        channel = None
    return {"configured": True, "connected": True, "channel": channel}


# ── Uploads em background ────────────────────────────────────────────────────

UPLOADS: dict[str, dict] = {}


def start_upload(clip_folder: Path) -> str:
    up_id = uuid.uuid4().hex[:8]
    UPLOADS[up_id] = {
        "id": up_id, "folder": str(clip_folder), "status": "enviando",
        "progress": 0, "url": None, "error": None, "started": time.time(),
    }
    threading.Thread(target=_upload, args=(up_id, clip_folder), daemon=True).start()
    return up_id


def _upload(up_id: str, folder: Path) -> None:
    state = UPLOADS[up_id]
    try:
        url = upload_clip(folder, lambda p: state.update(progress=round(p * 100)))
        state.update(status="concluído", progress=100, url=url)
    except Exception as e:  # noqa: BLE001 — erro vai para a UI
        state.update(status="erro", error=f"{type(e).__name__}: {e}")


def upload_clip(folder: Path, progress_cb: Callable[[float], None]) -> str:
    """Sobe folder/video.mp4 com os metadados de metadata.json. Retorna a URL."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = get_credentials()
    if not creds:
        raise RuntimeError("YouTube não conectado — clique em 'Conectar YouTube' primeiro")

    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    video = folder / "video.mp4"
    if not video.exists():
        raise FileNotFoundError(f"video.mp4 não encontrado em {folder}")

    up_cfg = CONFIG.get("upload", {})
    title = meta["title"][:100]
    if meta.get("kind") == "short" and "#shorts" not in title.lower():
        title = (title[:91] + " #Shorts") if len(title) > 91 else title + " #Shorts"

    body = {
        "snippet": {
            "title": title,
            "description": meta.get("description", ""),
            "tags": [t.lstrip("#") for t in meta.get("hashtags", [])][:30],
            "categoryId": str(up_cfg.get("category_id", "24")),
        },
        "status": {
            "privacyStatus": up_cfg.get("privacy", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }

    yt = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            progress_cb(progress.progress())

    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"

    thumb = folder / "thumbnail.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=video_id, media_body=str(thumb)).execute()
        except Exception:  # noqa: BLE001 — conta sem verificação de telefone não pode thumb
            pass

    meta["youtube_url"] = url
    (folder / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return url


# ── Biblioteca de cortes no disco ────────────────────────────────────────────

def library() -> list[dict]:
    """Todos os cortes em output/, com estado de upload (lido do metadata.json)."""
    clips = []
    out_root = path_for("output")
    for meta_file in sorted(out_root.glob("*/*/*/metadata.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        folder = meta_file.parent
        if not (folder / "video.mp4").exists():
            continue
        clips.append({
            "folder": str(folder),
            "episode": folder.parent.parent.name,
            "kind": meta.get("kind", "short"),
            "title": meta.get("title", folder.name),
            "description": meta.get("description", ""),
            "hashtags": meta.get("hashtags", []),
            "duration": meta.get("duration", 0),
            "video": str((folder / "video.mp4").relative_to(out_root)).replace("\\", "/"),
            "thumbnail": (folder / "thumbnail.jpg").exists(),
            "youtube_url": meta.get("youtube_url"),
        })
    return clips
