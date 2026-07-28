; Установщик KPGEN ESTP
; Собирается компилятором Inno Setup 6.

#define AppName "KPGEN ESTP"
#define AppVersion "1.0"
#define AppPublisher "ЕСТП"
#define AppURL "https://estp.ru"
#define AppExeName "KPGEN ESTP.exe"

[Setup]
AppId={{8F3C1E6A-4D2B-4C77-9E1A-3B7D5C2E1A04}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=KPGEN_ESTP_Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
DisableDirPage=no
DisableReadyPage=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
; Основная программа
Source: "..\dist\KPGEN ESTP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Запуск программы после установки
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function OllamaInstalled: Boolean;
var
  Path: String;
begin
  { Ollama ставится в профиль пользователя }
  Path := ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe');
  Result := FileExists(Path);
  if not Result then
    Result := FileExists(ExpandConstant('{autopf}\Ollama\ollama.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsDir := ExpandConstant('{userappdata}\KPGEN ESTP');
    if not DirExists(SettingsDir) then
      CreateDir(SettingsDir);

    { Ollama нужна только для текстов с помощью ИИ.
      Без неё программа работает в режиме «по правилам», поэтому
      установку не навязываем, а показываем понятную инструкцию. }
    if not OllamaInstalled then
      MsgBox(
        'Программа установлена.' + #13#10#13#10 +
        'Для подготовки текстов с помощью ИИ дополнительно нужна программа Ollama.' + #13#10 +
        'Без неё KPGEN ESTP тоже работает, но тексты будут более шаблонными.' + #13#10#13#10 +
        'Чтобы включить ИИ:' + #13#10 +
        '1. Скачайте Ollama с сайта ollama.com и установите;' + #13#10 +
        '2. Откройте командную строку и выполните:' + #13#10 +
        '     ollama pull qwen2.5:7b' + #13#10#13#10 +
        'Загрузка модели занимает около 4,7 ГБ и выполняется один раз.',
        mbInformation, MB_OK);
  end;
end;
