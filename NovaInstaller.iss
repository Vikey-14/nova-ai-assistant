; NovaInstaller.iss — Inno Setup script (updated for big multi-size icon)

[Setup]
AppId={{5D3B9F6B-6D46-4E8A-9E32-2B6F4C8E0A12}}
AppName=Nova
AppVersion=1.0.0
AppPublisher=Nova
DefaultDirName={autopf}\Nova
DefaultGroupName=Nova
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=NovaSetup
SetupIconFile=nova_icon_big.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NOVA.exe

; Per-user installs (no admin). {autopf} resolves to %LOCALAPPDATA%\Programs on per-user.
PrivilegesRequired=lowest

; Optional: If you ever want all-users (admin) installs, comment the line above and
; use:  ; PrivilegesRequired=admin
; and change the Startup shortcut below from {userstartup} to {commonstartup}.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked
Name: "autostart";   Description: "Start Nova Tray when I sign in to Windows"; Flags: checkedonce

[Files]
; Bundle everything PyInstaller produced (NOVA.exe and Nova Tray.exe live here)
Source: "dist\NOVA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Ship the big multi-size icon so shortcuts can reference it explicitly
Source: "nova_icon_big.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\Nova";      Filename: "{app}\NOVA.exe";      WorkingDir: "{app}"; IconFilename: "{app}\nova_icon_big.ico"
Name: "{group}\Nova Tray"; Filename: "{app}\Nova Tray.exe"; WorkingDir: "{app}"; IconFilename: "{app}\nova_icon_big.ico"

; Desktop shortcut (optional task)
Name: "{userdesktop}\Nova"; Filename: "{app}\NOVA.exe"; WorkingDir: "{app}"; IconFilename: "{app}\nova_icon_big.ico"; Tasks: desktopicon

; ✅ Auto-start (Startup folder) — per-user
; If you switch to all-users/admin install later, change to {commonstartup}.
Name: "{userstartup}\Nova Tray"; Filename: "{app}\Nova Tray.exe"; WorkingDir: "{app}"; Tasks: autostart

[Run]
; Start the tray immediately after install so the icon appears right away
Filename: "{app}\Nova Tray.exe"; Description: "Launch Nova Tray now"; Flags: nowait postinstall skipifsilent
