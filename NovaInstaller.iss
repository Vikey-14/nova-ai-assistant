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
DisableDirPage=yes
DisableProgramGroupPage=yes
WizardStyle=modern

; Core metadata
AppId={{B2F2778E-7A66-4F3C-8F6B-3E3B9F3A0F00}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Icons
SetupIconFile=assets\nova_icon_big.ico
UninstallDisplayIcon={app}\Nova\Nova.exe

; Install path
DefaultDirName={pf64}\Nova
DefaultGroupName=Nova

; Output
OutputDir=dist\installer
OutputBaseFilename=NovaSetup
Compression=lzma
SolidCompression=yes

; Make upgrades smoother
CloseApplications=force
RestartApplications=false
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
; Ensure our subfolder exists
Name: "{app}\Nova"

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

[InstallDelete]
; Belt-and-suspenders: remove any leftover per-user data BEFORE installing
Type: filesandordirs; Name: "{localappdata}\Nova"
Type: filesandordirs; Name: "{userappdata}\Nova"

[UninstallDelete]
; Wipe ALL per-user data on uninstall so a reinstall is a clean first-boot
Type: filesandordirs; Name: "{localappdata}\Nova"
Type: filesandordirs; Name: "{userappdata}\Nova"

[Run]
; Start the tray immediately so the taskbar icon is visible right after install.
; 'runasoriginaluser' ensures it runs as the invoking user even though installer runs elevated.
Filename: "{app}\Nova\Nova Tray.exe"; Flags: nowait postinstall skipifsilent runasoriginaluser
