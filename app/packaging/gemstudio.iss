; Inno Setup script for Gem Studio. Compile with (from app/):
;   ISCC.exe /DAppVersion=0.1.0 packaging\gemstudio.iss
; build_app.ps1 does this after the PyInstaller build and its self-test.
;
; Per-user install: no administrator rights, installs under %LOCALAPPDATA%\Programs. The user's
; saved replays (the cache in %LOCALAPPDATA%\GemStudio) are never touched by install or uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Gem Studio"
#define AppExe "GemStudio.exe"

[Setup]
; Keep this AppId fixed forever: it is how an upgrade finds the installed version.
AppId={{6F0C2F6E-9C4B-4F7A-8B61-3B0E5D2A91C7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Gem Studio
AppPublisherURL=https://github.com/bilalfawadkhan/gem-dota-uI
AppSupportURL=https://github.com/bilalfawadkhan/gem-dota-uI/issues
DefaultDirName={autopf}\GemStudio
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\build\installer
OutputBaseFilename=GemStudio-Setup-{#AppVersion}
SetupIconFile=gemstudio.ico
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\build\LICENSES.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "openwith"; Description: "List {#AppName} under ""Open with"" for .dem replay files"; GroupDescription: "File types:"

[Files]
Source: "..\build\dist\GemStudio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Offer, never force: .dem may already belong to another program.
Root: HKA; Subkey: "Software\Classes\GemStudio.dem"; ValueType: string; ValueData: "Dota 2 replay"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\GemStudio.dem\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\GemStudio.dem\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.dem\OpenWithProgids"; ValueType: string; ValueName: "GemStudio.dem"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
