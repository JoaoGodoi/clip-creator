@echo off
cd /d "%~dp0"

rem Ferramentas baixadas pelo instalador (ffmpeg, deno) ficam em ..\tools
set "PATH=%~dp0..\tools\ffmpeg;%~dp0..\tools\deno;%PATH%"
rem Instalado pelo .exe: o modelo do Whisper fica na pasta do app (sai junto na desinstalacao)
if exist "%~dp0..\tools" set "HF_HOME=%~dp0..\hf"

if not exist ".venv\Scripts\python.exe" (
    echo Projeto ainda nao instalado. Rode o instalador PodcastClipper-Setup.exe.
    pause
    exit /b 1
)

echo Atualizando o yt-dlp (o YouTube muda direto e versao velha da erro 403)...
.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]" -q --disable-pip-version-check

powershell -NoProfile -Command "if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) { Start-Process -FilePath ($env:LOCALAPPDATA + '\Programs\Ollama\ollama.exe') -ArgumentList 'serve' -WindowStyle Hidden; Write-Host 'Ollama iniciado.' }"

start "" http://localhost:8765
.venv\Scripts\python.exe -m uvicorn api:app --port 8765
