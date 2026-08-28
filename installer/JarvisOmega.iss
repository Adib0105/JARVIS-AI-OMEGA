#define MyAppName "JARVIS AI OMEGA"
#ifndef MyAppVersion
  #error MyAppVersion must be supplied by build_installer.ps1 from jarvis.version
#endif
#ifndef MyWindowsVersion
  #error MyWindowsVersion must be supplied by build_installer.ps1 from jarvis.version
#endif
#define MyAppPublisher "Adib Azam"
#define MyAppExeName "JARVIS-OMEGA.exe"

[Setup]
AppId={{A26A8779-4A69-4A6D-8DBD-0D3E88E8A701}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JARVIS AI OMEGA
DefaultGroupName=JARVIS AI OMEGA
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=JARVIS-AI-OMEGA-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyWindowsVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyWindowsVersion}
VersionInfoCompany={#MyAppPublisher}

[InstallDelete]
Type: files; Name: "{app}\JARVIS-OMEGA-V7.exe"
Type: files; Name: "{app}\JARVIS-OMEGA-V6.exe"

[Files]
Source: "..\dist\JARVIS-OMEGA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JARVIS AI OMEGA"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\JARVIS AI OMEGA"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Registry]
; Per-user startup keeps the assistant listening after Windows sign-in without
; requiring the full desktop window to be opened manually. The value is removed
; automatically on uninstall; profile data under LocalAppData is preserved.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JARVIS AI OMEGA"; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch JARVIS AI OMEGA"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
