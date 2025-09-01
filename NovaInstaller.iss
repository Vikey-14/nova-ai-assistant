; Inno Setup script for NOVA (Windows)

#define MyAppName "NOVA"

; Prefer CI-provided version (APPVER). If missing, try EXE file version; else fallback.
#define MyAppVersion GetEnv("APPVER")
#if MyAppVersion == ""
  #if FileExists("dist\\NOVA\\NOVA.exe")
    #define MyAppVersion GetVersionNumbersString("dist\\NOVA\\NOVA.exe")
  #else
    #define MyAppVersion "0.0.0"
  #endif
#endif

#define MyAppPublisher "NOVA"
#define MyAppExeName "NOVA.exe"

[Setup]
; ---- 64-bit install to Program Files (not x86) ----
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Require elevation for Program Files + registry writes
PrivilegesRequired=admin

; Core metadata
AppId={{B2F2778E-7A66-4F3C-8F6B-3E3B9F3A0F00}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Install path (explicitly 64-bit Program Files)
DefaultDirName={pf64}\NOVA
DefaultGroupName=NOVA

; Uninstaller icon in Apps & Features
UninstallDisplayIcon={app}\NOVA\NOVA.exe

; Output
OutputDir=dist\installer
OutputBaseFilename=NovaSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; Simple, no custom dir/group pages
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
; Start the tray immediately so the taskbar icon is visible right after install.
; 'runasoriginaluser' ensures it runs as the invoking user even though installer runs elevated.
Filename: "{app}\NOVA\NovaTray.exe"; Flags: nowait postinstall skipifsilent runasoriginaluser
