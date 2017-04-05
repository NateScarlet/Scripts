
@ECHO OFF

REM Set codepage to UTF-8
CHCP 65001 > nul

REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

ECHO 工程: %PROJECT% 集: %EP%

XCOPY /D /Y /V /I "%SERVER%\%PROJECT%\Comp\image\%EP%\%SCENE%" "%~dp0\images"

GOTO :EOF
