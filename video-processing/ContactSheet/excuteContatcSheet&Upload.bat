CHCP 936 > nul
TITLE 色板生成后_上传
SET "dateA=%date:~5,2%%date:~8,2%"
START /WAIT POWERSHELL -command "& '%~dp0excuteContactSheet.bat'"
XCOPY /Y /D /I "%~dp0ContactSheet*.png" "\\192.168.1.7\z\SNJYW\Comp\image\%dateA%"
REM PAUSE