# Instalador do Podcast Clipper: instala tudo e deixa o projeto pronto para usar.
# Pode rodar quantas vezes quiser: o que ja estiver instalado/baixado e pulado.
# (Sem acentos de proposito: o PowerShell 5.1 do Windows le .ps1 como ANSI.)

$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow }
function Fail($msg) {
    Write-Host ""
    Write-Host "ERRO: $msg" -ForegroundColor Red
    Write-Host "Tire um print desta janela e mande para quem te passou o projeto." -ForegroundColor Red
    exit 1
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Winget-Install($id) {
    winget install -e --id $id --accept-source-agreements --accept-package-agreements --silent
    Refresh-Path
}

function Find-Python {
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    return $null
}

function Find-FFmpeg {
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $pkgs = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
    if (Test-Path $pkgs) {
        $hit = Get-ChildItem $pkgs -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue |
               ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue } |
               Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    if (Test-Path 'C:\ffmpeg\bin\ffmpeg.exe') { return 'C:\ffmpeg\bin\ffmpeg.exe' }
    return $null
}

function Find-Ollama {
    $exe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $exe) { return $exe }
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Ollama-Up {
    try { Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 2 | Out-Null; return $true }
    catch { return $false }
}

Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "   Instalador do Podcast Clipper"              -ForegroundColor Magenta
Write-Host "   Pode demorar (uns 10 GB de download)."      -ForegroundColor Magenta
Write-Host "   NAO feche esta janela ate aparecer PRONTO." -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta

# ---------------------------------------------------------------- winget
Step "Conferindo o winget (instalador do Windows)"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Fail "winget nao encontrado. Instale o 'App Installer' pela Microsoft Store e rode o setup de novo."
}
Ok "winget encontrado"

# ---------------------------------------------------------------- Python
Step "Python 3.12"
$python = Find-Python
if (-not $python) {
    Write-Host "    Instalando Python 3.12..."
    Winget-Install 'Python.Python.3.12'
    $python = Find-Python
}
if (-not $python) { Fail "Python 3.12 nao instalou." }
Ok $python

# ---------------------------------------------------------------- FFmpeg
Step "FFmpeg (edicao de video)"
$ffmpeg = Find-FFmpeg
if (-not $ffmpeg) {
    Write-Host "    Instalando FFmpeg..."
    Winget-Install 'Gyan.FFmpeg'
    $ffmpeg = Find-FFmpeg
}
if (-not $ffmpeg) { Fail "FFmpeg nao instalou." }
Ok $ffmpeg

# ---------------------------------------------------------------- Deno
# O yt-dlp precisa de um runtime JavaScript para baixar do YouTube sem falhas.
Step "Deno (usado pelo yt-dlp para baixar do YouTube)"
if (-not (Get-Command deno -ErrorAction SilentlyContinue)) {
    Write-Host "    Instalando Deno..."
    Winget-Install 'DenoLand.Deno'
}
if (Get-Command deno -ErrorAction SilentlyContinue) { Ok "Deno instalado" }
else { Warn "Deno nao instalou. Downloads do YouTube podem falhar; o resto funciona." }

# ---------------------------------------------------------------- Ollama
Step "Ollama (IA local que escolhe os cortes)"
$ollama = Find-Ollama
if (-not $ollama) {
    Write-Host "    Instalando Ollama..."
    Winget-Install 'Ollama.Ollama'
    $ollama = Find-Ollama
}
if (-not $ollama) { Fail "Ollama nao instalou." }
Ok $ollama

if (-not (Ollama-Up)) {
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
    for ($i = 0; $i -lt 30 -and -not (Ollama-Up); $i++) { Start-Sleep -Seconds 1 }
}
if (-not (Ollama-Up)) { Fail "O Ollama nao abriu. Reinicie o PC e rode o setup de novo." }

$model = 'qwen3:8b'
$m = Select-String -Path (Join-Path $Root 'config.yaml') -Pattern '^\s*ollama_model:\s*(\S+)' | Select-Object -First 1
if ($m) { $model = $m.Matches[0].Groups[1].Value }

Step "Baixando o modelo de IA '$model' (~5 GB, demora)"
& $ollama pull $model
if ($LASTEXITCODE -ne 0) { Fail "Nao consegui baixar o modelo $model." }
Ok "modelo $model pronto"

# ---------------------------------------------------------------- venv + pip
Step "Ambiente Python do projeto (.venv)"
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    & $python -m venv (Join-Path $Root '.venv')
}
if (-not (Test-Path $venvPy)) { Fail "Nao consegui criar a .venv." }
Ok ".venv criada"

Step "Instalando bibliotecas Python"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail "pip install falhou." }

$nvidia = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
if ($nvidia) {
    Step "Placa NVIDIA encontrada ($($nvidia.Name)): instalando aceleracao da GPU (~3 GB)"
    & $venvPy -m pip install -r (Join-Path $Root 'requirements-gpu.txt')
    if ($LASTEXITCODE -ne 0) { Warn "Libs da GPU falharam; a transcricao vai rodar na CPU (mais lenta)." }
    else { Ok "GPU pronta" }
} else {
    Warn "Sem placa NVIDIA: a transcricao vai rodar na CPU (mais lenta, mas funciona)."
}

# ---------------------------------------------------------------- videos de fundo
# Fontes e licencas: assets\*\FONTES.md
$ffmpegDir = Split-Path $ffmpeg
$videoFmt = 'bv*[height<=1080][ext=mp4]/b[height<=1080][ext=mp4]'
$assets = @(
    @{ File = 'dopamine\subway_surfers.mp4';    Url = 'https://www.youtube.com/watch?v=i0M4ARe9v0Y'; Fmt = $videoFmt },
    @{ File = 'dopamine\gta_mega_ramp.mp4';     Url = 'https://www.youtube.com/watch?v=ZtLrNBdXT7M'; Fmt = $videoFmt },
    @{ File = 'dopamine\minecraft_parkour.mp4'; Url = 'https://www.youtube.com/watch?v=952ILTHDgC4'; Fmt = $videoFmt },
    @{ File = 'overlay\particles_bokeh.mp4';    Url = 'https://www.youtube.com/watch?v=Zg78emQ-lNw'; Fmt = $videoFmt },
    @{ File = 'overlay\space_stars.mp4';        Url = 'https://www.youtube.com/watch?v=Gsc0HtG6rTc'; Fmt = $videoFmt },
    @{ File = 'music\rose_water.m4a';           Url = 'https://www.youtube.com/watch?v=xakBzg5atsM'; Fmt = 'ba[ext=m4a]/ba' }
)

Step "Baixando videos de fundo dos shorts (~2 GB)"
foreach ($a in $assets) {
    $out = Join-Path $Root "assets\$($a.File)"
    if (Test-Path $out) { Ok "$($a.File) (ja existe)"; continue }
    Write-Host "    Baixando $($a.File)..."
    & $venvPy -m yt_dlp --no-playlist --ffmpeg-location $ffmpegDir -f $a.Fmt -o $out $a.Url
    if (Test-Path $out) { Ok $a.File }
    else { Warn "Falhou: $($a.File). O app funciona sem ele; rode o setup de novo depois para tentar." }
}

# ---------------------------------------------------------------- teste final
Step "Testando a instalacao"
& $venvPy -c "import fastapi, uvicorn, yt_dlp, faster_whisper, anthropic, PIL, yaml, googleapiclient; print('    imports OK')"
if ($LASTEXITCODE -ne 0) { Fail "Alguma biblioteca nao importou." }

# ---------------------------------------------------------------- atalho
Step "Criando atalho na Area de Trabalho"
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut((Join-Path $desktop 'Podcast Clipper.lnk'))
    $lnk.TargetPath = Join-Path $Root 'run.bat'
    $lnk.WorkingDirectory = $Root
    $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,18"
    $lnk.Save()
    Ok "atalho 'Podcast Clipper' criado"
} catch {
    Warn "Nao consegui criar o atalho. Use o run.bat da pasta do projeto."
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "   PRONTO! Tudo instalado."                    -ForegroundColor Green
Write-Host "   Para abrir: atalho 'Podcast Clipper' na"   -ForegroundColor Green
Write-Host "   Area de Trabalho (ou o run.bat)."           -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
exit 0
