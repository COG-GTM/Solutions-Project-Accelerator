@echo off
rem	 Library deployment script - v2 b20210115
rem  Run this file to deploy the libraries and templates contained in this download
echo ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
echo :: Library Deployment
echo ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

SETLOCAL ENABLEDELAYEDEXPANSION
SETLOCAL ENABLEEXTENSIONS

rem Set library name. This will be used as the base name of the file folder the libraries will be copied to.  This name will be appended with _[BuildID]
SET _Library=(SPA) Solutions Project Accelerator 1.0

rem  Identify Parent / Child
SET _parent=%~dp0
SET _me=%~n0

rem  Get parent folder name 
for %%I in ("%~dp0") do for %%J in ("%%~dpI.") do set _ParentFolderName=%%~nxJ
rem echo %_ParentFolderName%
	
rem  Isolate release build id
for /f "tokens=1* delims=_" %%a in ("%_ParentFolderName%") do set _ReleaseBuild=%%b

rem  Determing if release build exists
if [%_ReleaseBuild%]==[] ( set _ReleaseBuild=Undefined)

rem  Display P/L/B
echo Package:	%_ParentFolderName%
echo Library:	%_Library%
echo Build:		%_ReleaseBuild%
echo.


rem  Verify valid build number
echo :: -------------------
echo :: Identifying Build Number
echo :: -------------------
echo.
rem  If build number undefined, notify
if %_ReleaseBuild%==Undefined (
echo    -- Build Number could NOT be identified.  Build Number will be set to ZERO.
set _ReleaseBuild=00000000
) else (
echo    -- Build Number Identified
echo.
)

rem  Check if ACM is installed
echo :: ------------------- 
echo :: Verifying ACM Install Status
echo :: -------------------
echo. 
IF NOT EXIST "C:\Program Files\Rockwell Automation\Application Code Manager" (
	set _DepSts=Incomplete - Application Code Manager cannot be located at the default installation path
	goto DepEnd
)
echo    -- Installation Verified
echo.

rem  GetPath
FOR /F "tokens=3*" %%A IN ('REG.EXE QUERY "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /V "Common Documents" 2^>NUL ^| FIND "REG_SZ"') DO SET CommonDocs=%%B\Studio 5000

rem Copy Libraries
echo :: -------------------
echo :: Copying Libraries
echo :: -------------------
echo.
IF EXIST "%~dp0.\ApplicationCodeManagerLibraries" (
  robocopy "%~dp0.\ApplicationCodeManagerLibraries" "%CommonDocs%\Libraries\Application Code Manager\%_Library%_%_ReleaseBuild%" *.HSL4 *.HZ1 *.txt /e /copy:DAT /dcopy:DAT /NFL /NDL /NJH /NJS /nc /ns /np
  echo    -- Copy Complete
  echo.
) else (
  echo    -- File Folder Not Found:  .\ApplicationCodeManagerLibraries
  echo.
)

IF NOT Exist "%~dp0.\ApplicationCodeManagerLibraries" (
	set _DepSts=Incomplete - No Libraries to Register
	goto DepEnd
)

rem Assemble ACM import script
echo :: -------------------
echo :: Generating Library Registration Script
echo :: -------------------
echo.
echo    -- Be patient, the duration of this process varies based on library size
echo //ACM Library Registration Script > "%_parent%ACMCLI_RegisterLibraries.txt"
echo |set /p="RegisterLibrary " >> "%_parent%ACMCLI_RegisterLibraries.txt"
for /f "delims=" %%a in ('dir "%CommonDocs%\Libraries\Application Code Manager\%_Library%_%_ReleaseBuild%\"*.HSL4 /b/s/a:-d/o:e') do (
    echo|set /p=""%%a"," >> "%_parent%ACMCLI_RegisterLibraries.txt"   
)
echo    -- Script Complete
echo.

rem Run ACM Script
echo :: -------------------
echo :: Registering Libraries
echo :: -------------------
echo.
echo    -- Be patient, the duration of this process varies based on library size
"C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole\ACMConsole.exe" -p "%_parent%ACMCLI_RegisterLibraries.txt" 
echo    -- Registration Complete
echo.
del "%_parent%ACMCLI_RegisterLibraries.txt"
set _DepSts=Complete

:DepEnd
echo -------------------
echo Deployment %_DepSts%
echo -------------------
exit