
@ECHO OFF

REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("%~dp0path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

REM Check variable
IF "%EP%"=="" (
    ECHO 错误 - path.ini中未设置集场
    PAUSE & GOTO :EOF
)
IF "%SCENE%"=="" (
    ECHO 错误 - path.ini中未设置场
    PAUSE & GOTO :EOF
)

ECHO 工程: %PROJECT% 集: %EP% 场: %SCENE%
ECHO.

REM Upload
XCOPY /Y /D /I /V "N:\%PROJECT%\Shots\%EP%\Comp\Working\%SCENE%\mov\*.mov" "%SERVER%\%PROJECT%\Comp\mov\%EP%\%SCENE%\"
XCOPY /Y /D /I /V "N:\%PROJECT%\Shots\%EP%\Comp\Working\%SCENE%\mov\burn-in\*.mov" "%SERVER%\%PROJECT%\Comp\mov\%EP%\%SCENE%\burn-in\"
XCOPY /Y /D /I /V "N:\%PROJECT%\Shots\%EP%\Comp\Working\%SCENE%\images\*.jpg" "%SERVER%\%PROJECT%\Comp\image\%EP%\%SCENE%\"

CALL "N:\%PROJECT%\Shots\%EP%\Comp\Working\%SCENE%\DownloadImage.bat" 

CALL "N:\%PROJECT%\Shots\%EP%\Comp\Working\%SCENE%\ExecuteContactSheet&Upload.bat"

GOTO :EOF