; Instalador do Podcast Clipper (Inno Setup 6).
; Compilar:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\PodcastClipper.iss
; Saida:     installer\Output\PodcastClipper-Setup.exe
;
; O .exe so carrega o bootstrap.ps1 e o icone; o codigo e as dependencias
; sao baixados na hora da instalacao (veja bootstrap.ps1 / install.ps1).
; Instala por usuario, sem pedir admin.

#define AppName "Podcast Clipper"
#define AppVersion "1.0"

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
; Modelo de IA + bibliotecas da GPU + videos de fundo
ExtraDiskSpaceRequired=16000000000

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

; Apaga tudo menos a pasta output (os cortes ja gerados ficam).
; O Ollama e o modelo de IA ficam instalados: remova pelo Painel de Controle se quiser.
[UninstallDelete]
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
