@ECHO OFF
IF "%~1"=="" (
    CD /D "%~dp0"
    FORFILES /D -60 /C "CMD /C "%~0" "@path" "@isDir""
    FOR /F "delims=" %%i IN ('DIR /A:D /B "%~dp0" ^| FINDSTR /V /I "Archived" ^| FINDSTR /V /I "Library"') DO (
        ECHO 文件夹:%%~i
        FORFILES /S /D -60 /P "%~dp0%%~i" /C "CMD /C "%~0" "@path" "@isDir""
        FOR /F "delims=" %%j IN ('DIR /S /A:D /B "%~dp0%%~i"') DO (
            DIR /B "%%~j" | SORT /R | FINDSTR . 1>nul || RD "%%~j" && ECHO 删除空文件夹 "%%~j"
        )
        DIR /B "%%~i" | SORT /R | FINDSTR . 1>nul || RD "%%~i" && ECHO 删除空文件夹 "%%~i"
        )
    EXIT
)
SET "fullPath=%~1"
IF "%fullPath%"=="%~0" (EXIT)
IF "%~nx1%"=="desktop.ini" (
    CALL:CleanFile
)
IF "%~nx1%"=="Thumbs.db" (
    CALL:CleanFile
)
SET "dir=%~dp1%"
SET "customDirName=%~n0"
SET "customDirName=%customDirName:~10%"
SET "scriptDir=%~dp0"
CALL SET "targetDir=%%dir:%scriptDir%=%scriptDir%Archived%customDirName%\%%"
IF NOT EXIST "%targetDir%" (
    MKDIR "%targetDir%"
)
ECHO 文件: %~nx1
IF NOT "%~2"=="TRUE" (
    MOVE "%fullPath%" "%targetDir%"
) ELSE (
    RMDIR "%fullPath%\"
)
GOTO:EOF

:CleanFile
ATTRIB -S -H -R -A "%fullPath%"    
DEL "%fullPath%"
EXIT
