; KinderSortLite Inno Setup Script
; Compile with Inno Setup Compiler

[Setup]
; Setup program basic information
AppName=KinderSortLite
AppVersion=1.0
AppPublisher=Group 3
AppPublisherURL=https://github.com/lerlerchan/KinderSort
AppSupportURL=https://github.com/lerlerchan/KinderSort
AppUpdatesURL=https://github.com/lerlerchan/KinderSort
DefaultDirName={pf}\KinderSortLite
DefaultGroupName=KinderSortLite
AllowNoIcons=yes
; Install with admin privileges to ensure writing to Program Files
PrivilegesRequired=admin
; Output filename
OutputBaseFilename=KinderSortLiteSetup
; Compression settings
Compression=lzma2
SolidCompression=yes
; Setup icon
;SetupIconFile=icon.ico
; Uninstall information
UninstallDisplayIcon={app}\KinderSortLite.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copy ALL files from dist\main folder (including models in _internal!)
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\KinderSortLite"; Filename: "{app}\KinderSortLite.exe"
Name: "{group}\{cm:UninstallProgram,KinderSortLite}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KinderSortLite"; Filename: "{app}\KinderSortLite.exe"; Tasks: desktopicon

[Run]
; Option to launch program after installation
Filename: "{app}\KinderSortLite.exe"; Description: "{cm:LaunchProgram,KinderSortLite}"; Flags: nowait postinstall skipifsilent