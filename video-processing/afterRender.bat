
REM CALL :MovUpload "EPXX\XX"
GOTO :EOF

:MovUpload
XCOPY /Y /D /I /V "E:\SNJYW\%~1\mov\*.mov" "\\192.168.1.7\z\SNJYW\Comp\mov\%~1\"
XCOPY /Y /D /I /V "E:\SNJYW\%~1\mov\burn-in\*.mov" "\\192.168.1.7\z\SNJYW\Comp\mov\%~1\burn-in\"
XCOPY /Y /D /I /V "E:\SNJYW\%~1\images\*.jpg" "\\192.168.1.7\z\SNJYW\Comp\image\%~1\"
START /WAIT POWERSHELL -COMMAND "& '"E:\SNJYW\%~1\ExecuteContactSheet^&Upload.bat"'" 
GOTO :EOF