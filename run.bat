@echo off
cd /d "%~dp0"

powershell -NoProfile -Command "if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) { Start-Process -FilePath ($env:LOCALAPPDATA + '\Programs\Ollama\ollama.exe') -ArgumentList 'serve' -WindowStyle Hidden; Write-Host 'Ollama iniciado.' }"

start "" http://localhost:8765
.venv\Scripts\python.exe -m uvicorn api:app --port 8765
