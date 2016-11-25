@ECHO off
CHCP 65001
TITLE 生成色板
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""
REM
REM 在上方设置路径变量
REM
CHDIR /D "%~dp0images"
REM 删除缩略图缓存
ATTRIB -S -H Thumbs.db
DEL Thumbs.db
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
CHDIR /D "%~dp0"
FOR /F %%i IN ('DIR /B "ContactSheet*.nk"') DO (
    ECHO.
    ECHO 全尺寸渲染 %%~i
    ECHO.
    %NUKE% -x -f --cont "%%~i"
)
