; Build with /DAppVersion=<pyproject version>; unsigned preview, CPU only.
#ifndef AppVersion
  #error AppVersion is required
#endif
#define AppId "com.trybushenko.voicetoclipboard"
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
[Setup]
AppId={#AppId}
AppName=Voice to Clipboard
AppVersion={#AppVersion}
AppPublisher=Voice to Clipboard contributors
DefaultDirName={localappdata}\Programs\VoiceToClipboard
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist\installer
OutputBaseFilename=VoiceToClipboard-{#AppVersion}-windows-x64-cpu-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\VoiceToClipboard.exe
AppMutex=Local\VoiceToClipboard.Desktop.Runtime
CloseApplications=no
RestartApplications=no
LicenseFile=..\..\LICENSE
[Files]
Source: "..\..\dist\VoiceToClipboard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\Voice to Clipboard\Voice to Clipboard"; Filename: "{app}\VoiceToClipboard.exe"; Parameters: "--app-module voice_to_clipboard.ui.desktop_app --run"; WorkingDir: "{app}"
[Run]
Filename: "{app}\VoiceToClipboard.exe"; Description: "Launch Voice to Clipboard"; Parameters: "--app-module voice_to_clipboard.ui.desktop_app --run"; Flags: nowait postinstall skipifsilent
[Code]
function StartupCommand(): String;
begin
  Result := '"' + ExpandConstant('{app}\VoiceToClipboard.exe') + '" --app-module voice_to_clipboard.ui.desktop_app --run';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Value: String;
begin
  { Preserve enabled/disabled state; migrate the existing app-owned value only.
    No second startup task/shortcut, no settings/history writes. }
  if CurStep = ssPostInstall then
    if RegQueryStringValue(HKCU, '{#RunKey}', '{#AppId}', Value) then
      if Value <> '' then
        if not RegWriteStringValue(HKCU, '{#RunKey}', '{#AppId}', StartupCommand()) then
          RaiseException('Could not update Start at login. Disable and re-enable it in the tray menu.');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Value: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, '{#RunKey}', '{#AppId}', Value) then
      if (Value = StartupCommand()) or
         (Value = ExpandConstant('{app}\VoiceToClipboard.exe') + ' --app-module voice_to_clipboard.ui.desktop_app --run') then
        RegDeleteValue(HKCU, '{#RunKey}', '{#AppId}');
end;
