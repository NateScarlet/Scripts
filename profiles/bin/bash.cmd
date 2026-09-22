@echo off
setlocal EnableExtensions

rem --------------------------------------------------------------------
rem Forward all arguments to an MSYS2 bash.exe.
rem
rem Windows ships its own bash.exe (the WSL launcher) ahead of MSYS2 in
rem the default PATH, so this wrapper must live in a directory that comes
rem earlier. It resolves the MSYS2 install by itself, so no install path
rem is hard-coded here.
rem
rem Resolution order:
rem   1. BASH_PATH  explicit override, e.g.
rem      BASH_PATH=D:\path\to\msys64\usr\bin\bash.exe
rem   2. MSYS2_ROOT set inside MSYS2 shells
rem   3. PATH scan  first bash.exe that is not a Windows-provided stub
rem
rem Keep this file pure ASCII. cmd.exe reads .cmd files using the active
rem ANSI code page, so non-ASCII comments corrupt the parser. The symptom
rem of that corruption is:
rem   'exist' is not recognized as an internal or external command
rem --------------------------------------------------------------------

set "BASH_EXE="

if defined BASH_PATH if exist "%BASH_PATH%" set "BASH_EXE=%BASH_PATH%"

if not defined BASH_EXE if defined MSYS2_ROOT if exist "%MSYS2_ROOT%\usr\bin\bash.exe" set "BASH_EXE=%MSYS2_ROOT%\usr\bin\bash.exe"

if not defined BASH_EXE call :scan_path

if not defined BASH_EXE (
    echo [bash.cmd] ERROR: no MSYS2 bash.exe found. 1>&2
    echo [bash.cmd] Set BASH_PATH to the full path of bash.exe, or add 1>&2
    echo [bash.cmd] the MSYS2 usr\bin directory to PATH. 1>&2
    exit /b 9009
)

if "%~1"=="" goto :interactive

"%BASH_EXE%" %*
exit /b %ERRORLEVEL%

:interactive
"%BASH_EXE%" -l -i
exit /b %ERRORLEVEL%

rem --------------------------------------------------------------------
rem Walk PATH and take the first bash.exe that Windows does not provide.
rem --------------------------------------------------------------------
:scan_path
for %%D in ("%PATH:;=" "%") do if not defined BASH_EXE call :try_dir "%%~D"
exit /b

:try_dir
set "CANDIDATE=%~1\bash.exe"
if not exist "%CANDIDATE%" exit /b
if /i "%~1"=="%SystemRoot%\System32" exit /b
if /i "%~1"=="%LOCALAPPDATA%\Microsoft\WindowsApps" exit /b
set "BASH_EXE=%CANDIDATE%"
exit /b