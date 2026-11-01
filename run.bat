@echo off
cd /d "%~dp0"

rem Ferramentas baixadas pelo instalador (ffmpeg, deno) ficam em ..\tools
set "PATH=%~dp0..\tools\ffmpeg;%~dp0..\tools\deno;%PATH%"
rem Instalado pelo .exe: o modelo do Whisper fica na pasta do app (sai junto na desinstalacao)
if exist "%~dp0..\tools" set "HF_HOME=%~dp0..\hf"

rem Ollama: o do instalador fica em ..\ollama (modelos junto, porta propria 11435).
rem Sem ele (rodando direto do codigo), usa o Ollama normal do PC na 11434.
rem (if sem bloco de parenteses: caminhos com "(x86)" quebrariam o bloco)
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%~dp0..\ollama\ollama.exe" set "OLLAMA_EXE=%~dp0..\ollama\ollama.exe"
if exist "%~dp0..\ollama\ollama.exe" set "OLLAMA_HOST=127.0.0.1:11435"
if exist "%~dp0..\ollama\ollama.exe" set "OLLAMA_MODELS=%~dp0..\ollama\models"
if exist "%~dp0..\ollama\ollama.exe" set "PODCAST_OLLAMA_URL=http://127.0.0.1:11435"
if exist "%~dp0..\ollama\ollama.exe" set "OLLAMA_HOME_DIR=%~dp0..\ollama\home"

if not exist ".venv\Scripts\python.exe" (
    echo Projeto ainda nao instalado. Rode o instalador PodcastClipper-Setup.exe.
    pause
    exit /b 1
)

echo Atualizando o yt-dlp (o YouTube muda direto e versao velha da erro 403)...
.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]" -q --disable-pip-version-check --no-cache-dir

powershell -NoProfile -Command "$u = $env:PODCAST_OLLAMA_URL; if (-not $u) { $u = 'http://127.0.0.1:11434' }; try { Invoke-RestMethod ($u + '/api/version') -TimeoutSec 2 | Out-Null } catch { if ($env:OLLAMA_HOME_DIR) { New-Item -ItemType Directory -Force $env:OLLAMA_HOME_DIR | Out-Null; $env:USERPROFILE = $env:OLLAMA_HOME_DIR }; Start-Process -FilePath $env:OLLAMA_EXE -ArgumentList 'serve' -WindowStyle Hidden; Write-Host 'Ollama iniciado.' }"

start "" http://localhost:8765
.venv\Scripts\python.exe -m uvicorn api:app --port 8765
