#ifndef AppSource
  #error AppSource must point to the built PyInstaller onedir.
#endif
#ifndef AppDisplayName
  #define AppDisplayName "Qonic Audio"
#endif
#ifndef AppVersion
  #define AppVersion "5.0.0-beta.1"
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric "5.0.0.1"
#endif
#ifndef AppReleaseChannel
  #define AppReleaseChannel "Internal Beta"
#endif
#ifndef AppExeName
  #define AppExeName "Qonic_Audio_v5.0.0-beta.1.exe"
#endif
#ifndef InstallerBasename
  #define InstallerBasename "Qonic_Audio_v5.0.0-beta.1_Setup"
#endif
#ifndef InstallerOutputDir
  #define InstallerOutputDir "."
#endif
#ifndef ProjectLicense
  #define ProjectLicense "..\LICENSE"
#endif

[Setup]
AppId={{E0F70B5B-246D-4E81-A6B2-A2D8DFD4AF5D}
AppName={#AppDisplayName}
AppVersion={#AppVersion}
AppVerName={#AppDisplayName} {#AppVersion} ({#AppReleaseChannel})
VersionInfoVersion={#AppVersionNumeric}
VersionInfoDescription={#AppDisplayName} {#AppReleaseChannel} Installer
DefaultDirName={autopf}\{#AppDisplayName}
DefaultGroupName={#AppDisplayName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir={#InstallerOutputDir}
OutputBaseFilename={#InstallerBasename}
SetupIconFile=..\Assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile={#ProjectLicense}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
ChangesAssociations=no
CloseApplications=force
RestartApplications=no
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=no
UsePreviousLanguage=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "zhcn"; MessagesFile: "languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSES\Inno-Setup-License.txt"; DestDir: "{app}\LICENSES"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppDisplayName} ({#AppReleaseChannel})"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppDisplayName} ({#AppReleaseChannel})"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppDisplayName}}"; Flags: nowait postinstall skipifsilent

; User configuration, cache, logs, and temporary files live under LocalAppData.
; The uninstaller intentionally leaves that user data in place for upgrades.
