# Instala/atualiza tudo que o Podcast Clipper precisa. Sem winget e sem admin:
# cada ferramenta e baixada direto da fonte oficial para dentro da pasta do app.
# Chamado pelo bootstrap.ps1 (instalador .exe e atalho "Atualizar"), que ja
# baixou o codigo para <AppDir>\app. Pode rodar quantas vezes quiser.
#
#   <AppDir>\app      codigo do GitHub (+ .venv, assets, output)
#   <AppDir>\tools    uv, ffmpeg, deno
#   <AppDir>\python   Python gerenciado pelo uv
#
# (Sem acentos de proposito: o PowerShell 5.1 do Windows le .ps1 como ANSI.)
param([Parameter(Mandatory = $true)][string]$AppDir)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$App   = Join-Path $AppDir 'app'
$Tools = Join-Path $AppDir 'tools'
$Tmp   = Join-Path $AppDir 'tmp'
New-Item -ItemType Directory -Force $Tools, $Tmp | Out-Null

$env:UV_CACHE_DIR = Join-Path $AppDir 'cache'
# O Python e baixado por nos (secao Python); o uv nunca baixa nem instala um.
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:Path = "$Tools\ffmpeg;$Tools\deno;$Tools\uv;$env:Path"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host ""; Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }

function Download($url, $out) {
    Remove-Item $out -Force -ErrorAction SilentlyContinue
    curl.exe -L --fail --retry 3 --retry-delay 3 -# -o $out $url
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $out)) {
        try { Invoke-WebRequest $url -OutFile $out -UseBasicParsing } catch { }
    }
    return (Test-Path $out)
}

function Extract($zip, $dest) {
    Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $dest | Out-Null
    tar.exe -xf $zip -C $dest
    if ($LASTEXITCODE -ne 0) { Expand-Archive $zip $dest -Force }
}

# Baixa um zip e copia os .exe de dentro dele (em qualquer subpasta) para tools\<name>.
function Get-Tool($name, $exe, [string[]]$urls) {
    $dir = Join-Path $Tools $name
    if (Test-Path (Join-Path $dir $exe)) { Ok "$name (ja instalado)"; return }
    $zip = Join-Path $Tmp "$name.zip"
    $got = $false
    foreach ($u in $urls) { if (Download $u $zip) { $got = $true; break } }
    if (-not $got) { Fail "Nao consegui baixar $name. Confira a internet e tente de novo." }
    $x = Join-Path $Tmp "$name-x"
    Extract $zip $x
    New-Item -ItemType Directory -Force $dir | Out-Null
    Get-ChildItem $x -Recurse -Filter *.exe | Copy-Item -Destination $dir -Force
    Remove-Item $x, $zip -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path (Join-Path $dir $exe))) { Fail "$name baixou, mas $exe nao veio no pacote." }
    Ok $name
}

# ---------------------------------------------------------------- ferramentas
Step "Ferramentas (uv, FFmpeg, Deno)"
Get-Tool 'uv' 'uv.exe' @('https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip')
Get-Tool 'ffmpeg' 'ffmpeg.exe' @(
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
)
Get-Tool 'deno' 'deno.exe' @('https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip')
$uv = Join-Path $Tools 'uv\uv.exe'

# ---------------------------------------------------------------- Python
Step "Python 3.12 e ambiente do projeto"
# Python standalone (o mesmo build que o uv usaria), baixado direto para
# <AppDir>\python. Nao deixamos o uv instalar: ele cria uma junction
# "3.12 -> 3.12.x", e o Inno Setup liga o RedirectionGuard, que os processos
# filhos herdam e que bloqueia a junction (os error 448).
# Um Python do sistema tambem nao serve: pode ser desinstalado e levar a .venv junto.
$PythonUrl = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$PyDir = Join-Path $AppDir 'python'
$basePy = Join-Path $PyDir 'python.exe'
if (-not (Test-Path $basePy)) {
    # rmdir nao segue junctions: limpa a sobra de versoes antigas do instalador
    if (Test-Path $PyDir) { cmd /c rmdir /s /q "`"$PyDir`"" }
    $tgz = Join-Path $Tmp 'python.tar.gz'
    if (-not (Download $PythonUrl $tgz)) { Fail "Nao consegui baixar o Python. Confira a internet e tente de novo." }
    $x = Join-Path $Tmp 'python-x'
    Extract $tgz $x
    Move-Item (Join-Path $x 'python') $PyDir
    Remove-Item $x, $tgz -Recurse -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path $basePy)) { Fail "O Python baixou, mas nao consegui extrair." }

$venvPy = Join-Path $App '.venv\Scripts\python.exe'
$cfg = Join-Path $App '.venv\pyvenv.cfg'
if ((Test-Path $cfg) -and -not (Select-String -Path $cfg -Pattern ('^home = ' + [regex]::Escape($PyDir) + '\s*$') -Quiet)) {
    Write-Host "    Recriando a .venv com o Python proprio do app..."
    cmd /c rmdir /s /q "`"$(Join-Path $App '.venv')`""
}
if (-not (Test-Path $venvPy)) {
    # --seed poe o pip na venv: o run.bat usa para atualizar o yt-dlp
    & $uv venv --python $basePy --seed (Join-Path $App '.venv')
}
if (-not (Test-Path $venvPy)) { Fail "Nao consegui criar o ambiente Python." }
Ok ".venv pronta"

Step "Bibliotecas Python"
& $uv pip install --python $venvPy -r (Join-Path $App 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail "Falhou ao instalar as bibliotecas." }
# -r nao atualiza o que ja esta instalado; o yt-dlp precisa estar sempre na ultima versao
& $uv pip install --python $venvPy -U "yt-dlp[default]"
if ($LASTEXITCODE -ne 0) { Fail "Nao consegui atualizar o yt-dlp." }

$nvidia = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
if ($nvidia) {
    Step "Placa NVIDIA ($($nvidia.Name)): aceleracao da GPU (~3 GB)"
    & $uv pip install --python $venvPy -r (Join-Path $App 'requirements-gpu.txt')
    if ($LASTEXITCODE -ne 0) { Warn "Libs da GPU falharam; a transcricao vai rodar na CPU (mais lenta)." }
    else { Ok "GPU pronta" }
} else {
    Warn "Sem placa NVIDIA: a transcricao roda na CPU (mais lenta, mas funciona)."
}

# ---------------------------------------------------------------- Ollama
Step "Ollama (IA local que escolhe os cortes)"
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollama)) {
    $setup = Join-Path $Tmp 'OllamaSetup.exe'
    if (-not (Download 'https://ollama.com/download/OllamaSetup.exe' $setup)) {
        if (-not (Download 'https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe' $setup)) {
            Fail "Nao consegui baixar o Ollama. Confira a internet e tente de novo."
        }
    }
    Write-Host "    Instalando Ollama (1-2 min)..."
    Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -Wait
    Remove-Item $setup -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path $ollama)) { Fail "O Ollama nao instalou." }
Ok "Ollama instalado"

function Ollama-Up {
    try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; return $true }
    catch { return $false }
}
# O app do Ollama costuma subir sozinho depois de instalar, mas na primeira vez
# pode passar de 1 minuto. So liga o servidor na mao se nada estiver rodando.
for ($i = 0; $i -lt 180 -and -not (Ollama-Up); $i += 2) {
    if ($i -eq 10 -and -not (Get-Process 'ollama', 'ollama app' -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
    }
    Start-Sleep -Seconds 2
}
if (-not (Ollama-Up)) { Fail "O Ollama nao abriu. Reinicie o PC e clique em 'Atualizar Podcast Clipper'." }

$model = 'qwen3:8b'
$m = Select-String -Path (Join-Path $App 'config.yaml') -Pattern '^\s*ollama_model:\s*(\S+)' | Select-Object -First 1
if ($m) { $model = $m.Matches[0].Groups[1].Value }
Step "Modelo de IA '$model' (~5 GB na primeira vez)"
& $ollama pull $model
if ($LASTEXITCODE -ne 0) { Fail "Nao consegui baixar o modelo $model." }
Ok "modelo pronto"

# ---------------------------------------------------------------- videos de fundo
# Fontes e licencas: assets\*\FONTES.md
$videoFmt = 'bv*[height<=1080][ext=mp4]/b[height<=1080][ext=mp4]'
$assets = @(
    @{ File = 'dopamine\subway_surfers.mp4';    Url = 'https://www.youtube.com/watch?v=i0M4ARe9v0Y'; Fmt = $videoFmt },
    @{ File = 'dopamine\gta_mega_ramp.mp4';     Url = 'https://www.youtube.com/watch?v=ZtLrNBdXT7M'; Fmt = $videoFmt },
    @{ File = 'dopamine\minecraft_parkour.mp4'; Url = 'https://www.youtube.com/watch?v=952ILTHDgC4'; Fmt = $videoFmt },
    @{ File = 'overlay\particles_bokeh.mp4';    Url = 'https://www.youtube.com/watch?v=Zg78emQ-lNw'; Fmt = $videoFmt },
    @{ File = 'overlay\space_stars.mp4';        Url = 'https://www.youtube.com/watch?v=Gsc0HtG6rTc'; Fmt = $videoFmt },
    @{ File = 'music\rose_water.m4a';           Url = 'https://www.youtube.com/watch?v=xakBzg5atsM'; Fmt = 'ba[ext=m4a]/ba' }
)
Step "Videos de fundo dos shorts (~2 GB na primeira vez)"
foreach ($a in $assets) {
    $out = Join-Path $App "assets\$($a.File)"
    if (Test-Path $out) { Ok "$($a.File) (ja existe)"; continue }
    Write-Host "    Baixando $($a.File)..."
    & $venvPy -m yt_dlp --no-playlist --ffmpeg-location "$Tools\ffmpeg" -f $a.Fmt -o $out $a.Url
    if (Test-Path $out) { Ok $a.File }
    else { Warn "Falhou: $($a.File). O app funciona sem ele; 'Atualizar Podcast Clipper' tenta de novo." }
}

# ---------------------------------------------------------------- teste final
Step "Testando a instalacao"
& $venvPy (Join-Path $App 'tools\selftest.py')
if ($LASTEXITCODE -ne 0) { Fail "O teste da instalacao falhou (veja a mensagem acima)." }

Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
exit 0
