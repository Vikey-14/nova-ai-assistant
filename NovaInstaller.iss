; Inno Setup script for Nova (Windows)

#define MyAppName "Nova"

; Prefer CI-provided version (APPVER). If missing, try EXE file version; else fallback.
#define MyAppVersion GetEnv("APPVER")
#if MyAppVersion == ""
  #if FileExists("dist\\Nova\\Nova.exe")
    #define MyAppVersion GetVersionNumbersString("dist\\Nova\\Nova.exe")
  #else
    #define MyAppVersion "0.0.0"
  #endif
#endif

#define MyAppPublisher "Nova"
#define MyAppExeName "Nova.exe"

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

; Use the crisp app icon for the installer/uninstaller UI
SetupIconFile=assets\nova_icon_big.ico

; Install path
; NOTE: If you already shipped versions that installed to {pf64}\NOVA,
; keeping the same AppId means upgrades will default to the OLD dir.
; Change here to {pf64}\Nova for fresh installs; upgrades will still
; stick to the existing dir automatically.
DefaultDirName={pf64}\Nova
DefaultGroupName=Nova

; Uninstaller icon in Apps & Features
UninstallDisplayIcon={app}\Nova\Nova.exe

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
; Install the portable PyInstaller folder under {app}\Nova
; (this includes Nova.exe and "Nova Tray.exe")
Source: "dist\Nova\*"; DestDir: "{app}\Nova"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Start Menu shortcuts (user-visible labels)
Name: "{autoprograms}\Nova";      Filename: "{app}\Nova\Nova.exe"
Name: "{autoprograms}\Nova Tray"; Filename: "{app}\Nova\Nova Tray.exe"
; Desktop shortcut (main app only)
Name: "{autodesktop}\Nova";       Filename: "{app}\Nova\Nova.exe"

[Registry]
; Auto-start Nova Tray at user login (per-user)
; Extra quotes ensure correct path with the space in "Nova Tray.exe"
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Nova Tray"; ValueData: """{app}\Nova\Nova Tray.exe"""; Flags: uninsdeletevalue

[Run]
; Start the tray immediately so the taskbar icon is visible right after install.
; 'runasoriginaluser' ensures it runs as the invoking user even though installer runs elevated.
Filename: "{app}\Nova\Nova Tray.exe"; Flags: nowait postinstall skipifsilent runasoriginaluser
