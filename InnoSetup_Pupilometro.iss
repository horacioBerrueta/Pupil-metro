; Script de Inno Setup para Pupilómetro
[Setup]
AppName=Pupilómetro
AppVersion=1.3
DefaultDirName={autopf}\Pupilometro
DefaultGroupName=Pupilometro
PrivilegesRequired=lowest
OutputDir=.\Installer
OutputBaseFilename=Instalador_Pupilometro_v1.3
Compression=lzma2
SolidCompression=yes
SetupIconFile=

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Pupilometro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Pupilómetro"; Filename: "{app}\Pupilometro.exe"; WorkingDir: "{userdocs}"
Name: "{autodesktop}\Pupilómetro"; Filename: "{app}\Pupilometro.exe"; WorkingDir: "{userdocs}"; Tasks: desktopicon

[Run]
Filename: "{app}\Pupilometro.exe"; WorkingDir: "{userdocs}"; Description: "{cm:LaunchProgram,Pupilómetro}"; Flags: nowait postinstall skipifsilent
