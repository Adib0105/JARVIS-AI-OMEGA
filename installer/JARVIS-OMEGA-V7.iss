#define MyAppName "JARVIS AI OMEGA V7"
#define MyAppVersion "7.0.0"
#define MyAppPublisher "Adib Azam"
#define MyAppExeName "JARVIS-OMEGA-V7.exe"

[Setup]
AppId={{B61E7A68-4CB8-47CB-B46D-AD1B0D6A7007}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS-AI-OMEGA-V7
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=JARVIS-AI-OMEGA-V7-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\JARVIS-OMEGA-V7\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\JARVIS AI OMEGA V7"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\JARVIS AI OMEGA V7"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch JARVIS AI OMEGA V7"; Flags: nowait postinstall skipifsilent

; Runtime-created data, .env, OAuth tokens, backups and logs are intentionally not
; listed under [UninstallDelete]. The uninstaller must not silently delete user data.
