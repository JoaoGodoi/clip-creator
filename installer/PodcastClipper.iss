; Instalador do Podcast Clipper (Inno Setup 6).
; Compilar:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\PodcastClipper.iss
; Saida:     installer\Output\PodcastClipper-Setup.exe
;
; O .exe so carrega o bootstrap.ps1 e o icone; o codigo e as dependencias
; sao baixados na hora da instalacao (veja bootstrap.ps1 / install.ps1).
; Instala por usuario, sem pedir admin.

#define AppName "Podcast Clipper"
#define AppVersion "1.2"

[Setup]
AppId={{6E0B8F4A-3C1D-4E5B-9A7F-2D8C4B1E9F03}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=JoaoGodoi
AppPublisherURL=https://github.com/JoaoGodoi/clip-creator
DefaultDirName={localappdata}\PodcastClipper
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=PodcastClipper-Setup
SetupIconFile=clipper.ico
UninstallDisplayIcon={app}\clipper.ico
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
; Tudo fica na pasta escolhida: Ollama + modelo de IA, bibliotecas da GPU,
; videos de fundo e o modelo do Whisper
ExtraDiskSpaceRequired=18000000000

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "bootstrap.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "clipper.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\app\output"

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\app\run.bat"; WorkingDir: "{app}\app"; IconFilename: "{app}\clipper.ico"
Name: "{group}\{#AppName}"; Filename: "{app}\app\run.bat"; WorkingDir: "{app}\app"; IconFilename: "{app}\clipper.ico"
Name: "{group}\Fechar {#AppName}"; Filename: "{app}\app\stop.bat"; WorkingDir: "{app}\app"; IconFilename: "{app}\clipper.ico"
Name: "{group}\Atualizar {#AppName}"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\bootstrap.ps1"" -AppDir ""{app}"""; IconFilename: "{app}\clipper.ico"
Name: "{group}\Pasta dos cortes"; Filename: "{app}\app\output"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\app\run.bat"; WorkingDir: "{app}\app"; Description: "Abrir o {#AppName} agora"; Flags: postinstall nowait shellexec skipifsilent; Check: InstallOk

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"""; Flags: runhidden; RunOnceId: "StopServer"
; Ollama e qualquer outro processo rodando de dentro da pasta (senao os arquivos ficam presos)
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Get-Process | Where-Object {{ $_.Path -like '{app}\*' -and $_.Name -notlike 'unins*' } | Stop-Process -Force -ErrorAction SilentlyContinue"""; Flags: runhidden; RunOnceId: "StopAppProcs"

; Desinstalacao normal: apaga tudo (inclusive Ollama e modelo de IA, que ficam
; em {app}\ollama) menos a pasta output, com os cortes ja gerados.
; Se a pessoa escolher "apagar tudo" (pergunta no inicio da desinstalacao), o
; [Code] apaga tambem o output (veja CurUninstallStepChanged).
[UninstallDelete]
Type: filesandordirs; Name: "{app}\ollama"
Type: filesandordirs; Name: "{app}\hf"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\cache"
Type: filesandordirs; Name: "{app}\tmp"
Type: filesandordirs; Name: "{app}\app\.venv"
Type: filesandordirs; Name: "{app}\app\assets"
Type: filesandordirs; Name: "{app}\app\data"
Type: filesandordirs; Name: "{app}\app\clipper"
Type: filesandordirs; Name: "{app}\app\installer"
Type: filesandordirs; Name: "{app}\app\tools"
Type: filesandordirs; Name: "{app}\app\web"
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: files; Name: "{app}\app\*"

[Code]
var
  BootstrapOk: Boolean;
  FullWipe: Boolean;

function InstallOk: Boolean;
begin
  Result := BootstrapOk;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption :=
      'Baixando e instalando tudo (janela azul/preta). Na primeira vez demora bastante...';
    BootstrapOk :=
      Exec('powershell.exe',
           '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\bootstrap.ps1') +
           '" -AppDir "' + ExpandConstant('{app}') + '"',
           '', SW_SHOW, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
    if not BootstrapOk then
      MsgBox('A instalação não terminou. Mande um print da janela de erro para quem te passou o app.' + #13#10 + #13#10 +
             'Depois de resolver, use o atalho "Atualizar Podcast Clipper" no menu Iniciar ' +
             '(não precisa instalar de novo).', mbError, MB_OK);
  end;
end;

{ ---------------------------------------------------------------- desinstalacao }

function InitializeUninstall(): Boolean;
begin
  FullWipe := False;
  if not UninstallSilent then
    FullWipe := MsgBox(
      'Quer apagar TUDO do Podcast Clipper?' + #13#10 + #13#10 +
      'SIM: apaga também os cortes já gerados. Não sobra nada.' + #13#10 + #13#10 +
      'NÃO: apaga o app (inclusive o Ollama e o modelo de IA), mas guarda ' +
      'os cortes já gerados.',
      mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

procedure RunHidden(const Exe, Params: String);
var
  ResultCode: Integer;
begin
  Exec(Exe, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

{ Instalacoes antigas (antes da 1.2) punham o Ollama no C:. O install.ps1 migra
  isso ao atualizar; aqui cobre quem desinstala sem ter atualizado.
  So mexe no que o install.ps1 marcou como nosso: um Ollama que ja existia
  no PC fica, e dele so saem os modelos que nos baixamos. }
procedure WipeOllama;
var
  App, Ollama: String;
  Models: TArrayOfString;
  I: Integer;
begin
  App := ExpandConstant('{app}');
  Ollama := ExpandConstant('{localappdata}\Programs\Ollama');
  if FileExists(App + '\instalou-ollama.txt') then
  begin
    RunHidden('taskkill.exe', '/F /T /IM "ollama app.exe" /IM ollama.exe');
    if FileExists(Ollama + '\unins000.exe') then
      RunHidden(Ollama + '\unins000.exe', '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART');
    DelTree(Ollama, True, True, True);
    DelTree(ExpandConstant('{%USERPROFILE}\.ollama'), True, True, True);
    DelTree(ExpandConstant('{localappdata}\Ollama'), True, True, True);
  end
  else if FileExists(Ollama + '\ollama.exe') and LoadStringsFromFile(App + '\baixou-modelos.txt', Models) then
    for I := 0 to GetArrayLength(Models) - 1 do
      if Trim(Models[I]) <> '' then
        RunHidden(Ollama + '\ollama.exe', 'rm ' + Trim(Models[I]));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if not FullWipe then
    Exit;
  if CurUninstallStep = usUninstall then
    WipeOllama;
  if CurUninstallStep = usPostUninstall then
    DelTree(ExpandConstant('{app}'), True, True, True);
end;
