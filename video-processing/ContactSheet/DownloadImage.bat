@ECHO OFF

REM Set codepage to UTF-8
CHCP 65001 > nul

REM Set server path
REM 设置服务器路径
SET "sever=\\192.168.1.7\z"

REM Get parent folder name for shot name
CD /D %~dp0
CALL :basename %cd%
SET "shot=%basename%"

REM Get parent's parent folder name for episode name
CD..
CALL :basename %cd%
SET "ep=%basename%"

REM Get parent's parent's parent folder name for project name
CD..
CALL :basename %cd%
SET "project=%basename%"

REM Display info
ECHO 工程: %project% 集: %ep% 场: %shot% 

REM Excute copy
XCOPY /D /Y /V /I "%sever%\%project%\Comp\image\%ep%\%shot%" "%~dp0\images"

GOTO: EOF

REM Define function basename like os.path.basename in python
:basename
FOR /f %%i IN ("%1") DO (
    SET basename=%%~ni
)
GOTO :EOF
