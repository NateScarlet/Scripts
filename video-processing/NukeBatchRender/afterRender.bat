
GOTO :EOF
REM 删除上面那行以开启自动上传MOV

@ECHO OFF
CHCP 65001
TITLE 渲染后动作_v0.1
FOR %%i in (
"EP05\01",
"EP04\04",
) DO (
    ECHO 上传MOV: %%~i
    CALL :MovUpload "%%~i" 2>>error.txt
)
GOTO :EOF

:MovUpload
XCOPY /Y /D /I /V "E:\SNJYW\%~1\mov\*.mov" "\\192.168.1.7\z\SNJYW\Comp\mov\%~1\"
XCOPY /Y /D /I /V "E:\SNJYW\%~1\mov\burn-in\*.mov" "\\192.168.1.7\z\SNJYW\Comp\mov\%~1\burn-in\"
START /WAIT POWERSHELL -COMMAND "& '"E:\SNJYW\%~1\excuteContatcSheet^&Upload.bat"'" 
GOTO :EOF