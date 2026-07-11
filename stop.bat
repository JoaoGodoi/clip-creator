@echo off
echo Fechando o Podcast Clipper...

powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Write-Host '- Servidor (porta 8765): fechado' } else { Write-Host '- Servidor: ja estava fechado' }"

powershell -NoProfile -Command "$p = Get-Process 'ollama','ollama app' -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; Write-Host '- Ollama: fechado (VRAM da GPU liberada)' } else { Write-Host '- Ollama: ja estava fechado' }"

echo.
echo Tudo fechado. Para abrir de novo, use o run.bat.
pause
