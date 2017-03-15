
@ECHO OFF
CHCP 65001
SETLOCAL ENABLEDELAYEDEXPANSION
CD /D %~dp0
CLS

REM Set window title
SET "VERSION=1.01"
TITLE 生成色板后_上传v%VERSION%

REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

REM Prepare folder name
SET "DATE_=%DATE:~8,2%%DATE:~11,2%"
SET "TARGET_FOLDER=%SERVER%\%FOLDER%"
SET "TARGET=%TARGET_FOLDER%\%DATE_%"

ECHO 当前日期:	%DATE%
ECHO 上传至:	%TARGET%

IF NOT EXIST %TARGET_FOLDER% (
    ECHO 错误 - 目标文件夹不存在
    PAUSE&EXIT
)

START /WAIT POWERSHELL -command "& '"%~dp0ExecuteContactSheet.bat"'"

XCOPY /Y /D /I "%~dp0ContactSheet*.png" "%TARGET%"

START MSHTA vbscript:msgbox("渲染完成",64,"生成色板后_上传v%VERSION%")(window.close)
