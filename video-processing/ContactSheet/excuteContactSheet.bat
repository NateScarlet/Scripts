
@ECHO off
CHCP 65001
TITLE 生成色板v1.1
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""
REM
REM 在上方设置路径变量
REM
CHDIR /D "%~dp0images"
REM 删除缩略图缓存
ATTRIB -S -H Thumbs.db
DEL Thumbs.db 2>nul
ECHO 删除代理文件:
FOR /F %%i IN ('DIR /B "*_proxy.*"') DO (
    ECHO %%~i
    DEL "%%~i"
    )
ECHO 删除临时文件:
FOR /F %%i IN ('DIR /B "*.tmp"') DO (
     ECHO %%~i
     DEL "%%~i"
     )
IF EXIST "%~dp0OneShotOneImage.py" (
    ECHO 同镜头号只保留最新的单帧
    "%~dp0OneShotOneImage.py" "%~dp0images"
)

CHDIR /D "%~dp0"
FOR /F %%i IN ('DIR /B "ContactSheet*.nk"') DO (
    ECHO.
    ECHO 全尺寸渲染 %%~i
    ECHO.
    %NUKE% -x -f --cont "%%~i"
)
