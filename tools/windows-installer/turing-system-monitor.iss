; Instalador do Monitor da Tela Turing (versão Backa do turing-smart-screen-python)
; Gerado pelo GitHub Actions (.github/workflows/generate-windows-packages.yml) a partir dos binários do PyInstaller.

#define SourceDir "..\..\dist\turing-system-monitor\"
#define IconDir "..\..\res\icons\monitor-icon-17865\"
#define WizardDir "..\..\tools\windows-installer\"

#define MyAppName "Monitor da Tela Turing"
#define MyAppVersion GetStringFileInfo(SourceDir + "main.exe", PRODUCT_VERSION)
#define MyAppPublisher "Guilherme Backa (baseado no turing-smart-screen-python, de Matthieu Houdebine)"
#define MyAppURL "https://github.com/guibacka/monitor-tela-turing"
#define TaskName "Monitor da Tela Turing"

[Setup]
; AppId próprio: não conflita com o instalador do projeto original
AppId={{8F3C2A71-4B6E-4D2F-9C1A-6E5B7D0A3F42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=monitor-tela-turing-{#MyAppVersion}-windows
AllowNoIcons=yes
; Administrador: necessário para a tarefa agendada com privilégios máximos e para o driver PawnIO
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
WizardStyle=modern
WizardImageFile={#WizardDir}*.bmp
WizardSmallImageFile={#IconDir}*.bmp
SetupIconFile={#IconDir}icon.ico
UninstallDisplayIcon={app}\main.exe
LicenseFile=..\..\LICENSE
InfoBeforeFile={#WizardDir}Disclaimer.rtf
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "default"; Description: "Instalação padrão"; Flags: iscustom

[Components]
Name: "program"; Description: "Monitor da Tela Turing (programas)"; Flags: fixed; Types: default
Name: "themes"; Description: "Temas e presets padrão (alterações nos temas incluídos serão perdidas; temas próprios são mantidos)"; Types: default; Flags: disablenouninstallwarning
Name: "config"; Description: "Configuração padrão (config.yaml)"; Types: default; Flags: disablenouninstallwarning

[Tasks]
Name: "autostart"; Description: "Iniciar o monitor automaticamente ao entrar no Windows (recomendado)"; GroupDescription: "Inicialização:"
Name: "desktopicon"; Description: "Criar atalhos na área de trabalho"; GroupDescription: "Atalhos:"

[Dirs]
; O editor e o configurador rodam como usuário comum e gravam temas/configuração na pasta do programa
Name: "{app}"; Permissions: users-modify

[Files]
Source: "{#SourceDir}*"; Excludes: "config.yaml,themes"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs; Components: program
Source: "{#SourceDir}config.yaml"; DestDir: "{app}"; Flags: ignoreversion; Components: config
Source: "{#SourceDir}res\themes\*"; Excludes: "--Theme examples"; DestDir: "{app}\res\themes\"; Flags: ignoreversion recursesubdirs; Components: themes
Source: "{#WizardDir}criar-tarefa.ps1"; DestDir: "{app}"; Flags: ignoreversion; Components: program
Source: "{#WizardDir}remover-tarefa.ps1"; DestDir: "{app}"; Flags: ignoreversion; Components: program
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\Editor de Tela"; Filename: "{app}\editor.exe"; WorkingDir: "{app}"; Comment: "Editor visual dos presets da tela"
Name: "{group}\Iniciar Monitor da Tela"; Filename: "{app}\iniciar-monitor.exe"; WorkingDir: "{app}"; Comment: "Inicia o monitor (se já estiver rodando, não faz nada)"
Name: "{group}\Configurar Monitor da Tela"; Filename: "{app}\configure.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Editor de Tela"; Filename: "{app}\editor.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\Iniciar Monitor da Tela"; Filename: "{app}\iniciar-monitor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Tarefa agendada: inicia o monitor ao entrar no Windows, como administrador, sem pedir confirmação
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\criar-tarefa.ps1"" -AppDir ""{app}"""; Flags: runhidden waituntilterminated; StatusMsg: "Criando a inicialização automática..."; Tasks: autostart
Filename: "{app}\iniciar-monitor.exe"; Description: "Iniciar o monitor da tela agora"; Flags: postinstall nowait skipifsilent; Tasks: autostart
Filename: "{app}\configure.exe"; Description: "Abrir a configuração"; Flags: postinstall nowait skipifsilent unchecked

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\remover-tarefa.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoverTarefa"

[UninstallDelete]
; Arquivos gerados pelo monitor durante o uso
Type: files; Name: "{app}\.monitor.pid"
Type: files; Name: "{app}\.monitor.state"
Type: files; Name: "{app}\.live-preview-*.png"
Type: files; Name: "{app}\log.log"

[Code]
(* Detecta se o programa já está instalado (atualização) *)
function IsUpgrade: Boolean;
var
    Value: string;
    UninstallKey: string;
begin
    UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
        ExpandConstant('{#SetupSetting("AppId")}') + '_is1';
    Result := (RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', Value) or
        RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', Value)) and (Value <> '');
end;

(* Na primeira instalação pula a página de componentes: instala tudo *)
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectComponents) and not IsUpgrade;
end;

(* Antes de copiar arquivos numa atualização: fecha o monitor/editor desta instalação, mantendo a tarefa *)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\remover-tarefa.ps1')) then
    Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
      ExpandConstant('{app}\remover-tarefa.ps1') + '" -KeepTask', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

(* Página para instalar o driver PawnIO (temperaturas e sensores) *)
var
  PagePawnIO: TWizardPage;
  InstallPawnIOCheckBox: TNewCheckBox;
  InfoText: TNewStaticText;

procedure CreatePagePawnIO;
begin
  PagePawnIO := CreateCustomPage(
    wpInstalling,
    'Instalar o driver PawnIO',
    'Recomendado para mostrar temperaturas e sensores'
  );

  InfoText := TNewStaticText.Create(PagePawnIO);
  InfoText.Parent := PagePawnIO.Surface;
  InfoText.Left := ScaleX(0);
  InfoText.Top := ScaleY(10);
  InfoText.Width := PagePawnIO.SurfaceWidth;
  InfoText.Height := ScaleY(70);
  InfoText.WordWrap := True;
  InfoText.Caption :=
    'O PawnIO é um driver de código aberto (assinado digitalmente) usado pelo LibreHardwareMonitor para ler os sensores do PC.' + #13#10 +
    'Sem ele, a temperatura do processador, clocks e outros dados ficam limitados ou indisponíveis.' + #13#10 +
    'Mais informações: https://pawnio.eu/';

  InstallPawnIOCheckBox := TNewCheckBox.Create(PagePawnIO);
  InstallPawnIOCheckBox.Parent := PagePawnIO.Surface;
  InstallPawnIOCheckBox.Caption := 'Instalar / atualizar o driver PawnIO';
  InstallPawnIOCheckBox.Left := ScaleX(0);
  InstallPawnIOCheckBox.Top := InfoText.Top + InfoText.Height + ScaleY(20);
  InstallPawnIOCheckBox.Width := PagePawnIO.SurfaceWidth;
  InstallPawnIOCheckBox.Font.Style := [fsBold];
  InstallPawnIOCheckBox.Checked := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
  Setup: String;
begin
  (* Não remover! *)
  Result := True;

  if CurPageID = PagePawnIO.ID then
  begin
    if InstallPawnIOCheckBox.Checked then
    begin
      Setup := ExpandConstant('{app}\external\PawnIO\PawnIO_setup.exe');
      if not FileExists(Setup) then
        MsgBox(Setup + ' não encontrado', mbError, MB_OK)
      else
      begin
        if not ShellExec('', Setup, '-uninstall -silent', ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
          MsgBox('Falha ao executar o PawnIO_setup.exe.'#13#10 + 'Código do erro: ' + IntToStr(ResultCode), mbError, MB_OK);
        if not ShellExec('', Setup, '-install -silent', ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
          MsgBox('Falha ao executar o PawnIO_setup.exe.'#13#10 + 'Código do erro: ' + IntToStr(ResultCode), mbError, MB_OK);
      end;
    end;
  end;
end;

procedure InitializeWizard;
begin
  (* Numa atualização, por padrão não sobrescreve temas e configuração (para não perder alterações) *)
  if IsUpgrade then begin
    Log('Atualização detectada');
    WizardSelectComponents('program !themes, !config');
    end
  else begin
    Log('Primeira instalação');
    WizardSelectComponents('program themes config');
  end;

  CreatePagePawnIO();
end;
