#ifndef MyAppVersion
  #error MyAppVersion must be supplied by build_installer.ps1
#endif
#ifndef MyAppName
  #error MyAppName must be supplied by build_installer.ps1
#endif
#ifndef MyAppExeName
  #error MyAppExeName must be supplied by build_installer.ps1
#endif
#ifndef MyArtifactName
  #error MyArtifactName must be supplied by build_installer.ps1
#endif
#ifndef MyInstallerBase
  #error MyInstallerBase must be supplied by build_installer.ps1
#endif

#define MyAppPublisher "Adib Azam"

[Setup]
AppId={{B61E7A68-4CB8-47CB-B46D-AD1B0D6A7007}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS-AI-OMEGA-V7.5
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename={#MyInstallerBase}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\{#MyArtifactName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Runtime-created data, .env, OAuth tokens, backups and logs are intentionally not
; listed under [UninstallDelete]. The uninstaller must not silently delete user data.
