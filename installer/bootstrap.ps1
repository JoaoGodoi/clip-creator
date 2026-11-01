# Vai dentro do instalador .exe. Baixa a versao mais nova do codigo do GitHub
# para <AppDir>\app e roda o installer\install.ps1 dela. Assim, correcoes no
# processo de instalacao chegam por git push, sem precisar gerar outro .exe.
# O atalho "Atualizar Podcast Clipper" roda este mesmo script.
#
# (Sem acentos de proposito: o PowerShell 5.1 do Windows le .ps1 como ANSI.)
param([Parameter(Mandatory = $true)][string]$AppDir)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'JoaoGodoi/clip-creator'
$Branch = 'main'
$App = Join-Path $AppDir 'app'
$Tmp = Join-Path $AppDir 'tmp'

New-Item -ItemType Directory -Force $AppDir | Out-Null
try { Start-Transcript -Path (Join-Path $AppDir 'install-log.txt') -Force | Out-Null } catch { }

function Done($code) {
    try { Stop-Transcript | Out-Null } catch { }
    Write-Host ""
    if ($code -eq 0) {
        Write-Host "=============================================" -ForegroundColor Green
        Write-Host "   PRONTO! Podcast Clipper instalado."          -ForegroundColor Green
        Write-Host "=============================================" -ForegroundColor Green
        Start-Sleep -Seconds 4
    } else {
        Write-Host "Deu erro. Tire um print desta janela e mande para quem te passou o app," -ForegroundColor Red
        Write-Host "junto com o arquivo $AppDir\install-log.txt" -ForegroundColor Red
        Read-Host "Aperte Enter para fechar"
    }
    exit $code
}

Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "   Instalando o Podcast Clipper"               -ForegroundColor Magenta
Write-Host "   Na primeira vez baixa uns 10 GB: demora."   -ForegroundColor Magenta
Write-Host "   NAO feche esta janela."                     -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta

# Fecha o app se estiver aberto (senao os arquivos ficam presos)
$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($c) { $c.OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }

Write-Host ""
Write-Host "==> Baixando o codigo do GitHub" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $Tmp, $App | Out-Null
$zip = Join-Path $Tmp 'code.zip'
$url = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
curl.exe -L --fail --retry 3 --retry-delay 3 -s -o $zip $url
if (-not (Test-Path $zip)) { try { Invoke-WebRequest $url -OutFile $zip -UseBasicParsing } catch { } }
if (-not (Test-Path $zip)) {
    Write-Host "ERRO: nao consegui baixar o codigo. Confira a internet." -ForegroundColor Red
    Done 1
}

$x = Join-Path $Tmp 'code'
Remove-Item $x -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $x | Out-Null
tar.exe -xf $zip -C $x
if ($LASTEXITCODE -ne 0) { Expand-Archive $zip $x -Force }
$src = Get-ChildItem $x -Directory | Select-Object -First 1
if (-not $src) { Write-Host "ERRO: o pacote do codigo veio vazio." -ForegroundColor Red; Done 1 }

# Atualiza o codigo mantendo o config.yaml de quem ja usa (e .venv/assets/output,
# que nao existem no zip e por isso nao sao tocados).
$keep = @()
if (Test-Path (Join-Path $App 'config.yaml')) { $keep = @('/XF', 'config.yaml') }
robocopy $src.FullName $App /E /NFL /NDL /NJH /NJS /NP @keep | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Host "ERRO: nao consegui copiar o codigo para $App." -ForegroundColor Red; Done 1 }
Remove-Item $x, $zip -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "    OK: codigo em $App" -ForegroundColor Green

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $App 'installer\install.ps1') -AppDir $AppDir
Done $LASTEXITCODE
