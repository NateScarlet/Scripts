
CHCP 936 > nul
@ECHO OFF
TITLE 色板生成后_上传
SET "dateA=%date:~5,2%%date:~8,2%"

SET "folderA="\\192.168.1.7\z\SNJYW\Comp\image\%dateA%""
REM ↑设置上传目标文件夹路径 %dateA%代表当前月日

ECHO 当前日期:	%dateA%
ECHO 上传目标文件夹:	%folderA%
START /WAIT POWERSHELL -command "& '"%~dp0excuteContactSheet.bat"'"
XCOPY /Y /D /I "%~dp0ContactSheet*.png" %folderA%
REM PAUSE