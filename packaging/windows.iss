#define AppVersion "0.7.0"
[Setup]
AppId={{AD1C5389-D3FC-49CB-B0C8-054789A4F636}
AppName=SPARKLE CODER
AppVersion={#AppVersion}
AppPublisher=SPARKLE CODER
DefaultDirName={localappdata}\SPARKLE CODER
DefaultGroupName=SPARKLE CODER
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\out
OutputBaseFilename=SPARKLE-CODER-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\SparkleCoder.exe
[Files]
Source: "..\dist\SparkleCoder.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\SPARKLE CODER"; Filename: "{app}\SparkleCoder.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\SPARKLE CODER"; Filename: "{app}\SparkleCoder.exe"; WorkingDir: "{app}"
[Run]
Filename: "{app}\SparkleCoder.exe"; Description: "Open SPARKLE CODER"; Flags: nowait postinstall skipifsilent
; PROJECTS and APP_DATA are deliberately absent from install/uninstall deletion rules.
