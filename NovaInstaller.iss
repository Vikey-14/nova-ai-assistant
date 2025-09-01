; Inno Setup script for NOVA (Windows)
#define MyAppName "NOVA"
#define MyAppVersion GetVersionNumbersString("dist\NOVA\NOVA.exe")
#define MyAppPublisher "NOVA"
#define MyAppExeName "NOVA.exe"

[Setup]
AppId={{B2F2778E-7A66-4F3C-8F6B-3E3B9F3A0F00}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\NOVA
DefaultGroupName=NOVA
OutputDir=dist\installer
OutputBaseFilename=NovaSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableDirPage=yes
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Install the portable PyInstaller folder under {app}\NOVA
; (this includes NOVA.exe and NovaTray.exe)
Source: "dist\NOVA\*"; DestDir: "{app}\NOVA"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Start Menu shortcuts (both will be searchable):
Name: "{autoprograms}\NOVA";      Filename: "{app}\NOVA\NOVA.exe"
Name: "{autoprograms}\Nova Tray"; Filename: "{app}\NOVA\NovaTray.exe"
; Desktop shortcut (main app only)
Name: "{autodesktop}\NOVA";       Filename: "{app}\NOVA\NOVA.exe"


[Registry]
; Auto-start Nova Tray at user login (per-user)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Nova Tray"; ValueData: """{app}\NOVA\NovaTray.exe"""; Flags: uninsdeletevalue


[Run]
; Start the tray immediately so the taskbar icon is visible right after install
Filename: "{app}\NOVA\NovaTray.exe"; Flags: nowait postinstall skipifsilent runasoriginaluser

