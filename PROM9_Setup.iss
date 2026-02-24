; ============================================
; PROM-9™ Installer Script
; ============================================

#define MyAppName "PROM-9™ Prompt Engine"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Sansebas Systems"
#define MyAppExeName "PromptEngine_PROM9.exe"

[Setup]
AppId={{A1C7F2C0-9B5A-4F91-8F0C-112233445566}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PROM9
DefaultGroupName=PROM9
OutputDir=.
OutputBaseFilename=PROM9_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=icono_app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones adicionales:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icono_app.ico"; DestDir: "{app}"; Flags: ignoreversion

; Seed opcional (la app lo copiará a %APPDATA%\PROM9 si no existe)
Source: "seed\*"; DestDir: "{app}\seed"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PROM-9™"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PROM-9™"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar PROM-9™"; Flags: nowait postinstall skipifsilent