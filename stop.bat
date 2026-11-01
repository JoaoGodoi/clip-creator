@echo off
echo Fechando o Podcast Clipper...

powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Write-Host '- Servidor (porta 8765): fechado' } else { Write-Host '- Servidor: ja estava fechado' }"

rem Instalado pelo .exe: fecha so o Ollama da pasta do app (um Ollama do PC fica rodando)
if exist "%~dp0..\ollama\ollama.exe" goto own_ollama
powershell -NoProfile -Command "$p = Get-Process 'ollama','ollama app' -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; Write-Host '- Ollama: fechado (VRAM da GPU liberada)' } else { Write-Host '- Ollama: ja estava fechado' }"
goto done

:own_ollama
powershell -NoProfile -Command "$d = (Resolve-Path -LiteralPath '%~dp0..\ollama').Path; $p = Get-Process ollama -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ($d + '\*') }; if ($p) { $p | Stop-Process -Force; Write-Host '- Ollama: fechado (VRAM da GPU liberada)' } else { Write-Host '- Ollama: ja estava fechado' }"

:done
echo.
echo Tudo fechado. Para abrir de novo, use o atalho Podcast Clipper.
pause
