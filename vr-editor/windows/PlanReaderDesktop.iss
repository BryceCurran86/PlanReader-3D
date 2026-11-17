#define AppName "PlanReader VR Desktop Preview"
#define AppVersion "0.1.0"
#define AppExeName "PlanReaderDesktop.exe"
[Setup]
AppId={{E97552C0-E55B-4574-8E96-B05CA4BE384E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PlanReader
DefaultDirName={localappdata}\Programs\PlanReader VR Desktop Preview
DefaultGroupName=PlanReader VR Desktop Preview
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=out\installer
OutputBaseFilename=PlanReader-VR-Desktop-Preview-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
[Files]
Source: "out\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\PlanReader VR Desktop Preview"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\PlanReader VR Desktop Preview"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch PlanReader VR Desktop Preview"; Flags: nowait postinstall skipifsilent
