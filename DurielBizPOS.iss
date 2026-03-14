#define MyAppName "DurielBiz POS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DurielBiz"
#define MyAppExeName "DurielBizPOS.exe"
#define MyAdminExeName "DurielBizPOSAdmin.exe"
#define MySyncServiceExeName "DurielBizPOSSyncService.exe"

[Setup]
AppId={{7A09D088-39A1-4302-B502-0D157A1D5FE7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\DurielBizPOS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=DurielBizPOS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAdminExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\DurielBizPOSSyncService\*"; DestDir: "{app}\sync-service"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\DurielBizPOS"
Type: filesandordirs; Name: "{localappdata}\DurielBizPOS"
