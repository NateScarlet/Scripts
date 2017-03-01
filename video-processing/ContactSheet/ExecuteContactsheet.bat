@ECHO off

REM Set codepage to UTF-8
CHCP 65001

REM Set window title
TITLE 生成色板v1.22

REM SET 'nuke.exe' path
REM 设置'nuke.exe'路径
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""

REM Set working directory to images folder
CHDIR /D "%~dp0images"

REM delete Thumbs.db
REM 删除缩略图缓存
ATTRIB -S -H Thumbs.db
DEL Thumbs.db 0>nul

REM Delete proxy file(disabled)
IF 1 == 0 (
    ECHO 删除代理文件:
    FOR /F %%i IN ('DIR /B "*_proxy.*"') DO (
        ECHO %%~i
        DEL "%%~i"
        )
)

REM Delete any .tmp file
ECHO 删除临时文件:
FOR /F %%i IN ('DIR /B "*.tmp"') DO (
     ECHO %%~i
     DEL "%%~i"
     )
     
REM Try keep only one newest image for same shot
IF EXIST "%UserProfile%\AppData\Local\Programs\Python" (
    IF EXIST "%~dp0OneShotOneImage.py" (
        ECHO 同镜头号只保留最新的单帧
        "%~dp0OneShotOneImage.py" "%~dp0images"
    )
)

REM Set working directory to current folder
CHDIR /D "%~dp0"

REM Execute contactsheet
FOR /F %%i IN ('DIR /B "ContactSheet*.nk"') DO (
    ECHO.
    ECHO 全尺寸渲染 %%~i
    ECHO.
    %NUKE% -x -f -c 8G --cont --priority low "%%~i"
)
