@ECHO OFF 

SET "el=None"
SET "SCRIPTS="\\SERVER\scripts\comp\ae""
SET "SCRIPT_UI="\\SERVER\scripts\comp\ScriptUI.jsx""
SET "STARTUP="\\SERVER\scripts\comp\Startup.jsx""
SET "SHUTDOWN="\\SERVER\scripts\comp\Shutdown.jsx""

SETLOCAL enabledelayedexpansion

call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CC 2017\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CC 2016\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CC 2015\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CC 2014\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CC\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS6\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS5\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS4\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS3\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS2\Support Files\Scripts"
call :linkdir "%ProgramFiles%\Adobe\Adobe After Effects CS\Support Files\Scripts"
call :linkdir "D:\Program Files\Adobe\Adobe After Effects CS6\Support Files\Scripts"

ECHO.
IF %el%==None (
    ECHO 没找到AE安装文件夹
) ELSE  IF %el%==1 (
    ECHO 请用管理员权限运行
) ELSE IF %el%==ignore (
    ECHO 文件夹已存在, 如要覆盖请手动删除
) ELSE IF %el%==0 (
    ECHO 已成功安装
    ECHO 在AE菜单 "文件" -^> "脚本"下可以找到服务器上的脚本
)
PAUSE

:linkdir
IF EXIST "%~1" (
    CD /D "%~1"
    IF EXIST comp (
        SET "el=ignore"
        GOTO :EOF 
    )
    MKLINK /D "comp" %SCRIPTS%
    MKLINK "ScriptUI Panels\吾立方.jsx" %SCRIPT_UI%
    MKLINK "Startup\custom_startup.jsx" %STARTUP%
    MKLINK "Shutdown\custom_shutdown.jsx" %SHUTDOWN%
    SET "el=!ERRORLEVEL!"
)
GOTO :EOF