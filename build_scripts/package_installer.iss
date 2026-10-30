
; Repo root, derived from this script's own location so the build is machine-independent.
#define RepoRoot ExtractFileDir(ExtractFileDir(SourcePath))
#define MyAppName "Solutions Project Accelerator"
#define MyAppVersion GetVersionNumbersString (RepoRoot + "\dist\runme\runme.exe")
#define MyAppId "77FA12AD-7031-433E-BFCF-EECC53AC1D6C"
#define MyAppPublisher "Rockwell Automation"
#define MyAppURL "https://www.rockwellautomation.com"
#define MyAppExeName "runme.exe"
#define MyAppAssocName MyAppName + " Project"
#define MyAppAssocExt ".aip"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DefaultDirName={autopf}\{#MyAppName}
ChangesAssociations=yes
DisableProgramGroupPage=yes
VersionInfoVersion={#MyAppVersion}
LicenseFile={#RepoRoot}\LICENSE
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
; Lets unattended test installs pass /CURRENTUSER and skip the UAC prompt.
PrivilegesRequiredOverridesAllowed=commandline
OutputDir={#RepoRoot}\build\installer
OutputBaseFilename=solutions_project_accelerator_setup
SetupIconFile={#RepoRoot}\bin\logo.ico
UninstallDisplayIcon={#RepoRoot}\bin\logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[InstallDelete]
; Logs written by earlier versions could contain the SQL Server password.
Type: files; Name: "{app}\_internal\temp\logfile.log*"

[Dirs] 
Name: "{app}\_internal\temp"; Permissions: users-modify
Name: "{app}\_internal\projects"; Permissions: everyone-full
Name: "{app}\acm_libraries"; Permissions: everyone-full
Name: "{app}\_internal\Ollama"; Permissions: everyone-full
Name: "{app}\_internal\Ollama\models"; Permissions: everyone-full
Name: "{app}\_internal\Ollama\models\blobs"; Permissions: everyone-full
Name: "{app}\_internal\Ollama\models\manifests"; Permissions: everyone-full

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\dist\runme\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\dist\runme\*"; DestDir: "{app}"; Excludes: "\_internal\temp\logfile.log"; Flags: ignoreversion recursesubdirs createallsubdirs
; SPA required libraries
Source: "{#RepoRoot}\build_scripts\acm_library_register.cmd"; DestDir: "{app}\acm_libraries"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\acm_libraries\ApplicationCodeManagerLibraries\(SPA)_Solutions_Project_Accelerator_DesignPattern_Other_Image_(1.8).HSL4"; DestDir: "{app}\acm_libraries\ApplicationCodeManagerLibraries"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\acm_libraries\ApplicationCodeManagerLibraries\(SPA)_Solutions_Project_Accelerator_DesignPattern_Other_PageLink_(1.5).HSL4"; DestDir: "{app}\acm_libraries\ApplicationCodeManagerLibraries"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\acm_libraries\ApplicationCodeManagerLibraries\(SPA)_Solutions_Project_Accelerator_DesignPattern_Other_ProcessLine_(1.6).HSL4"; DestDir: "{app}\acm_libraries\ApplicationCodeManagerLibraries"; Flags: ignoreversion recursesubdirs createallsubdirs
; Demo documents for the training manual. Listed explicitly so Excel lock files
; and personal working copies in the source folder cannot ship.
Source: "{#RepoRoot}\data\Test P&ID\Demo\DEMO_P&ID.pdf"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\DEMO_P&ID.xlsx"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\Simple Control Philosophy.pdf"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\H0001.xml"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\DisplaysImport.txt"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\BatchImport_Demo_Video_ProjectHMI.xml"; DestDir: "{app}\demo"; Flags: ignoreversion
Source: "{#RepoRoot}\data\Test P&ID\Demo\SEAddComponent_Demo_Video_ProjectHMI.xml"; DestDir: "{app}\demo"; Flags: ignoreversion
; Ollama required files
; ollama.exe is a single file - recursesubdirs/createallsubdirs here would mirror every
; subdir of Ollama\ (incl. the gitignored model store) as empty dirs.
Source: "{#RepoRoot}\Ollama\ollama.exe"; DestDir: "{app}\_internal\Ollama"; Flags: ignoreversion
; CUDA runners are ~1.8 GB and push the setup past Inno's 2100000000-byte single-file ceiling.
Source: "{#RepoRoot}\Ollama\lib\*"; DestDir: "{app}\_internal\Ollama\lib"; Excludes: "cuda_v12,cuda_v13"; Flags: ignoreversion recursesubdirs


[Registry]
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppAssocKey}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".myp"; ValueData: ""

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Code]
{ ///////////////////////////////////////////////////////////////////// }
function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\77FA12AD-7031-433E-BFCF-EECC53AC1D6C_is1');
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;


{ ///////////////////////////////////////////////////////////////////// }
function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;


{ ///////////////////////////////////////////////////////////////////// }
function UnInstallOldVersion(): Integer;
var
  sUnInstallString: String;
  iResultCode: Integer;
  ProgressPage: TOutputProgressWizardPage;
begin
{ Return Values: }
{ 1 - uninstall string is empty }
{ 2 - error executing the UnInstallString }
{ 3 - successfully executed the UnInstallString }

  { default return value }
  Result := 0;

  { get the uninstall string of the old app }
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then begin
    // Create a progress page
    ProgressPage := CreateOutputProgressPage('Upgrading Installation', 
      'Removing previous version of ' + ExpandConstant('{#MyAppName}') + '...');
    
    try
      // Show the progress page
      ProgressPage.Show;
      ProgressPage.SetProgress(10, 100);
      ProgressPage.SetText('Preparing to uninstall previous version...', '');
      
      // Use a less silent uninstall to show some progress
      sUnInstallString := RemoveQuotes(sUnInstallString);
      
      // Update progress
      ProgressPage.SetProgress(30, 100);
      ProgressPage.SetText('Uninstalling previous version...', 'This may take a moment.');
      
      // Run the uninstaller with fewer silent flags to show more progress
      // Use /SILENT instead of /VERYSILENT to show some visual feedback
      sUnInstallString := RemoveQuotes(sUnInstallString);
      if Exec(sUnInstallString, '/SILENT /NORESTART /NOCANCEL','', SW_HIDE, ewWaitUntilTerminated, iResultCode) then begin
        // Update progress on success
        ProgressPage.SetProgress(90, 100);
        ProgressPage.SetText('Previous version removed successfully.', 'Continuing with installation...');
        Sleep(1000); // Give user a moment to see the success message
        Result := 3;
      end else begin
        // Update progress on failure
        ProgressPage.SetText('Failed to uninstall previous version.', 'Installation will continue, but may not be complete.');
        Sleep(2000); // Give user time to read the error
        Result := 2;
      end;

      finally
      // Hide and free the progress page
      ProgressPage.Hide;
    end;
  end else
    Result := 1;
end;

{ ///////////////////////////////////////////////////////////////////// }
procedure PreserveFolders(const InstallPath: String);
var
  InternalDir: String;
  ProjectDir: String;
begin
  if not DirExists(InstallPath) then
    exit;
    
  // Create _internal directory if it doesn't exist
  InternalDir := InstallPath + '\_internal';
  if not DirExists(InternalDir) then
    CreateDir(InternalDir);


  // Move projects folder if it exists
  ProjectDir := InstallPath + '\projects';
  if DirExists(ProjectDir) then begin
    Log('Moving project folder to _internal');
    if not RenameFile(ProjectDir, InternalDir + '\projects') then
      Log('Failed to move project folder');
  end;
end;

{ ///////////////////////////////////////////////////////////////////// }
procedure CleanUpOldInstall(const Path: String);
var
  FindRec: TFindRec;
  InternalDir: String;
begin
  if not DirExists(Path) then
    exit;

  InternalDir := Path + '\_internal';
  
  if FindFirst(Path + '\*', FindRec) then begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
          if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then begin
            // Skip _internal directory
            if CompareText(Path + '\' + FindRec.Name, InternalDir) <> 0 then begin
              Log('Removing directory: ' + Path + '\' + FindRec.Name);
              DelTree(Path + '\' + FindRec.Name, True, True, True);
            end;
          end else begin
            Log('Removing file: ' + Path + '\' + FindRec.Name);
            DeleteFile(Path + '\' + FindRec.Name);
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;


{ ///////////////////////////////////////////////////////////////////// }
procedure CurStepChanged(CurStep: TSetupStep);
var
  InstallPath: String;
begin
  if (CurStep=ssInstall) then begin

    // Get the current installation path
    InstallPath := ExpandConstant('{app}');
    
    if (IsUpgrade()) then begin
      UnInstallOldVersion();
    end;

    if DirExists(InstallPath) then begin
      Log('Existing installation found at: ' + InstallPath);
      
      // First preserve the folders we want to keep
      PreserveFolders(InstallPath);
      
      // Then clean up everything else
      CleanUpOldInstall(InstallPath);
    end 
  end;
end;

[Run]
Filename: "{app}\acm_libraries\acm_library_register.cmd"; Description: "Register Solutions Project Accelerator libraries"; Flags: postinstall skipifsilent runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

