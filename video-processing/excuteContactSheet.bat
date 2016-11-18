@ECHO off
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""
REM
REM 在上方设置路径变量
REM
CHDIR /D "%~dp0images"
ECHO 删除代理文件:
FOR /F %%i IN ('DIR /B "*_proxy.*"') DO (DEL "%%~i")
ECHO 删除临时文件:
FOR /F %%i IN ('DIR /B "*.tmp"') DO (DEL "%%~i")
CHDIR /D "%~dp0"
FOR /F %%i IN ('DIR /B "ContactSheet*.nk"') DO (
    ECHO.
    ECHO 全尺寸渲染 %%~i
    ECHO.
    %NUKE% -x -f --cont "%%~i"
)
EXIT