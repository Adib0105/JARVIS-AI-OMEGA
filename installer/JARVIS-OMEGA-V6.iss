#define MyAppName "JARVIS AI OMEGA V6"
#define MyAppVersion "6.0.0"
#define MyAppPublisher "Adib Azam"
#define MyAppExeName "JARVIS-OMEGA-V6.exe"

[Setup]
AppId={{B61E7A68-4CB8-47CB-B46D-AD1B0D6A6006}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS-AI-OMEGA-V6
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=JARVIS-AI-OMEGA-V6-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}

[Files]
Source: "..\dist\JARVIS-OMEGA-V6\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\JARVIS AI OMEGA V6"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\JARVIS AI OMEGA V6"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch JARVIS AI OMEGA V6"; Flags: nowait postinstall skipifsilent
