@ECHO OFF
CHCP 65001 > nul
IF "%~2"=="" (
    TITLE 本地化素材v1.3
)
REM
REM 默认服务器地址
SET "serverDefault=\\192.168.1.7\z"
REM
SET "serverDir=%~2"
IF "%~2"=="" (
    SET "serverDir=%serverDefault%"
)
:BatchRuning
IF "%~1"=="" (
    FOR %%i in ("%~dp0\*.nk") do (
    	ECHO.
    	ECHO %%~ni
    	ECHO.
    	CALL:LocaliseFootage "%%~i" "%serverDir%"
    )
    ECHO ----------------
    ECHO 全部素材缓存完毕
    ECHO ----------------
    IF "%~2"=="" (
        PAUSE
    )
    GOTO:EOF
)
:LocaliseFootage
SET "localDir=%NUKE_TEMP_DIR%\localize\Z_"
SET "agrv1=%~n1%"
SETLOCAL EnableDelayedExpansion
FOR /F "delims=_|. tokens=1-4" %%i in ("%agrv1%") do (
    SET "project=%%i"
    SET "ep=%%j"
    SET "sc=%%k"
    SET "shot=%%l"

)
ECHO. 
ECHO 工程:%project% 集:%ep% 场:%sc% 镜头:%shot%
ECHO.
ECHO 将服务器素材下载到本地...
FOR /F "delims=" %%m IN ('FINDSTR /R /C:"^ *file "^""*Z:" "%~1"') do (
    FOR /F "tokens=* delims= " %%i IN ("%%~m") DO (SET "footagePath=%%~i")
    SET "footagePath=!footagePath:~5!"
    FOR /F "delims=" %%n IN ("!footagePath!") DO (
        SET "footagePath=%%~n"
    )
    SET "footagePath=!footagePath:/=\!"
    SET "footagePath=!footagePath:%%d=*!"
    SET "footagePath=!footagePath:%%01d=*!"
    SET "footagePath=!footagePath:%%02d=*!"
    SET "footagePath=!footagePath:%%03d=*!" 
    SET "footagePath=!footagePath:%%04d=*!" 
    SET "footagePath=!footagePath:%%0d=*!" 
    SET "footagePath=!footagePath:#=*!" 
    CALL SET "cacheDir=!footagePath:Z:\=%localDir%\!"
    CALL SET "footagePath=!footagePath:Z:\=%serverDir%\!"
    FOR /F "delims=" %%n IN ("!cacheDIR!") DO (
        SET "cacheDir=%%~dpn"
    )    
    ECHO "!footagePath!" -^> "!cacheDir!"
    XCOPY /Y /D /V /I "!footagePath!" "!cacheDir!"
    IF ERRORLEVEL 4 (
        ECHO 找不到文件 - "!footagePath!" >> "%~dp0LocaliseLog.txt"
        ECHO. >> "%~dp0LocaliseLog.txt"
    )
)
ECHO.
ECHO %~1 素材缓存完毕
ECHO.
IF EXIST "%~dp0LocaliseLog.txt" (
    ECHO -----错误日志----
)
TYPE "%~dp0LocaliseLog.txt" 2>nul
ECHO.
IF EXIST "%~dp0LocaliseLog.txt" (
    CHOICE /T 15 /D n /M "手动进行检查?"
    IF "!ERRORLEVEL!" EQU "1" (
        EXPLORER "%~dp0LocaliseLog.txt"
        EXPLORER "!footagePath!"
        EXPLORER "!cacheDir!"
        PAUSE
    )
)
DEL "%~dp0LocaliseLog.txt" 2>nul
IF "%~2"=="" (
    PAUSE
)
GOTO:EOF