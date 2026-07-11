# 🎬 Podcast Clipper

App local que transforma episódios de podcast do YouTube em cortes prontos para publicar:

- **Cortes longos** (10–12 min, 16:9) com intro/ending, título, descrição e thumbnail.
- **Shorts/Reels** (9:16) com legenda automática palavra-a-palavra queimada no vídeo.

Tudo roda na sua máquina: download (yt-dlp), transcrição (faster-whisper na GPU) e
edição (ffmpeg). Só a **seleção dos melhores cortes** usa a API do Claude.

## Como usar

1. Dê dois cliques em `run.bat` (abre http://localhost:8765).
2. Cole a URL do canal → escolha um vídeo → aguarde o pipeline.
3. Os arquivos ficam em `output/<episódio>/longos/` e `output/<episódio>/shorts/`,
   cada corte com `video.mp4`, `descricao.txt`, `metadata.json` (+ `thumbnail.jpg` nos longos).

## Configuração

| O quê | Onde |
|---|---|
| Chave da API (seleção de cortes) | variável de ambiente `ANTHROPIC_API_KEY` — sem ela o app roda em modo **mock** (cortes de teste em posições fixas) |
| Intro / ending dos cortes longos | `assets/intro.mp4` e `assets/outro.mp4` (opcionais) |
| Nome do podcast (créditos), nº de cortes, modelo do Whisper | `config.yaml` |

Para definir a chave permanentemente (PowerShell):

```powershell
setx ANTHROPIC_API_KEY "sua-chave-aqui"
```

## Instalação (já feita)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
# ffmpeg via: winget install Gyan.FFmpeg
```

## Roadmap

- [x] Fase 1 — pipeline completo + interface web
- [ ] Fase 2 — upload automático via YouTube Data API (OAuth; app não verificado sobe como privado + `publishAt`)
- [ ] Fase 3 — monitoramento automático do canal (rodar sem intervenção)
- [ ] Extras — enquadramento com rastreamento de rosto nos shorts
