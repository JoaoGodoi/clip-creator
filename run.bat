@echo off
cd /d "%~dp0"
start "" http://localhost:8765
.venv\Scripts\python.exe -m uvicorn api:app --port 8765
