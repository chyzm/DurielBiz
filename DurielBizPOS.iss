#define MyAppName "DurielBiz POS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DurielTech"
#define MyAppExeName "DurielBizPOS.exe"
#define MyAdminExeName "DurielBizPOSAdmin.exe"

[Setup]
AppId={{7A09D088-39A1-4302-B502-0D157A1D5FE7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://durieltech.com.ng
AppSupportURL=https://durieltech.com.ng
AppUpdatesURL=https://durieltech.com.ng
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
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAdminExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\DurielBizPOS"
Type: filesandordirs; Name: "{localappdata}\DurielBizPOS"

[Code]
var
  PairingPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  if not FileExists(ExpandConstant('{localappdata}\DurielBizPOS\sync_credentials.json')) then
  begin
    PairingPage := CreateInputQueryPage(wpSelectDir,
      'Link this desktop to a cloud business',
      'Enter the referral key from that business''s Cloud Business Settings.',
      'The key links this installation to the correct business and is exchanged for a private device credential.');
    PairingPage.Add('Business referral key:', True);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (PairingPage <> nil) and (CurPageID = PairingPage.ID) then
  begin
    Result := Trim(PairingPage.Values[0]) <> '';
    if not Result then
      MsgBox('Enter the cloud business referral key to continue.', mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  KeyPath: string;
begin
  if (CurStep = ssPostInstall) and (PairingPage <> nil) then
  begin
    KeyPath := ExpandConstant('{localappdata}\DurielBizPOS\referral-key.txt');
    ForceDirectories(ExtractFileDir(KeyPath));
    SaveStringToFile(KeyPath, Trim(PairingPage.Values[0]) + #13#10, False);
  end;
end;
