
@ECHO OFF
CHCP 65001
SETLOCAL ENABLEDELAYEDEXPANSION
CD /D %~dp0
CLS

REM Set window title
TITLE 生成色板v1.3

REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

REM Set working directory to images folder
CHDIR /D "%~dp0images"

REM Delete thumbs.db
IF EXIST thumbs.db (
    ATTRIB -S -H thumbs.db
    DEL Thumbs.db
)

REM Delete any .tmp file
IF EXIST *.tmp (
    ECHO 删除临时文件:
    FOR /F %%i IN ('DIR /B "*.tmp"') DO (
         ECHO %%~i
         DEL "%%~i"
    )
)

REM Keep only one newest image for same shot
ECHO 同镜头号只保留最新的单帧
%NUKE% -t "%~dp0OneShotOneImage.py" "%~dp0images"

REM Execute contactsheet
FOR /F %%i IN ('DIR /B "ContactSheet*.nk"') DO (
    ECHO.
    ECHO 全尺寸渲染 %%~i
    ECHO.
    %NUKE% -x -f -c 8G --cont --priority low "%%~i"
)

GOTO :EOF