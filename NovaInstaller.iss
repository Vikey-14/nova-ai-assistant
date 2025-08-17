; NovaInstaller.iss — put this file at your project root (same level as dist/)
; Requires: Inno Setup (https://jrsoftware.org/isinfo.php)

[Setup]
AppId={{5D3B9F6B-6D46-4E8A-9E32-2B6F4C8E0A12}
AppName=Nova
AppVersion=1.0.0
DefaultDirName={autopf}\Nova
DefaultGroupName=Nova
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=NovaSetup
SetupIconFile=nova_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

; If you want per-user (no admin) installs, uncomment the next line and adjust icons to {userdesktop}/{userstartup}
; PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Bundle everything PyInstaller produced for BOTH apps
Source: "dist\NOVA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Start Menu shortcuts
Name: "{group}\Nova";       Filename: "{app}\NOVA.exe";      WorkingDir: "{app}"; IconFilename: "{app}\nova_icon.ico"
Name: "{group}\Nova Tray";  Filename: "{app}\Nova Tray.exe"; WorkingDir: "{app}"; IconFilename: "{app}\nova_icon.ico"

; Desktop shortcut for the main app
Name: "{commondesktop}\Nova"; Filename: "{app}\NOVA.exe"; WorkingDir: "{app}"; IconFilename: "{app}\nova_icon.ico"

; Startup shortcut so the tray icon is *always there* after login
; Use {commonstartup} for all users (requires admin). For per-user only, switch to {userstartup}.
Name: "{commonstartup}\Nova Tray"; Filename: "{app}\Nova Tray.exe"; WorkingDir: "{app}"

[Run]
; Start the tray immediately after install so the icon appears right away
Filename: "{app}\Nova Tray.exe"; Description: "Start Nova Tray now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nothing special needed—shortcuts get removed automatically.
