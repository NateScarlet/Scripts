@ECHO OFF
IF NOT EXIST "%~1" (
    ECHO 提示 - 必须把nk文件拖到此文件上打开来使用
    PAUSE&GOTO:EOF
)
SET "serverDir=%~2"
IF NOT EXIST "%~2" (
    SET "serverDir=\\192.168.1.7\z"
    REM 默认服务器地址
)
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
FOR /F "delims=" %%m IN ('FINDSTR /R /C:"^ *file Z:" "%~1"') do (
    FOR /F "tokens=* delims= " %%i IN ("%%~m") DO (SET "footagePath=%%~i")
    SET "footagePath=!footagePath:~5!"
    FOR /F "delims=" %%n IN ("!footagePath!") DO (
        SET "footagePath=%%~n"
    )
    SET "footagePath=!footagePath:/=\!"
    SET "footagePath=!footagePath:%%d=*!" 
    SET "footagePath=!footagePath:%%04d=*!" 
    SET "footagePath=!footagePath:####=*!" 
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
    IF "%ERRORLEVEL%" EQU "1" (
        EXPLORER "%~dp0LocaliseLog.txt"
        EXPLORER "!footagePath!"
        EXPLORER "!cacheDir!"
        PAUSE
    )
)
DEL "%~dp0LocaliseLog.txt" 2>nul