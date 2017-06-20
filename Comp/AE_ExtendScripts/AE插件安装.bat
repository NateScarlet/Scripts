@ECHO OFF 
SET "el=None"
SET "SCRIPTS="\\SERVER\scripts\comp\ae""
SETLOCAL enabledelayedexpansion

call :linkdir "C:\Program Files\Adobe\Adobe After Effects CC 2017\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CC 2016\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CC 2015\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CC\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS6\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS5\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS4\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS3\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS2\Support Files\Scripts"
call :linkdir "C:\Program Files\Adobe\Adobe After Effects CS\Support Files\Scripts"

IF %el%==None (
    ECHO 没找到AE安装文件夹
)
IF %el%==1 (
    ECHO 请用管理员权限运行
)
IF %el%==ignore (
    ECHO 文件夹已存在, 如要覆盖请手动删除
)
IF %el%==0 (
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
    SET "el=!ERRORLEVEL!"
)
GOTO :EOF