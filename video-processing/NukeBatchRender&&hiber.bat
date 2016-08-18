@echo off
setlocal enabledelayedexpansion
for %%i in ("%~dp0\*.nk") do (
	echo.
	echo !date! !time:~0,8!	[Start]	%%i >>RenderLog.txt
	echo.
	nuke10.0.exe -x -f %%i 
	echo.
	echo !date! !time:~0,8!	[Finish]	%%i >>Renderlog.txt
	echo.
)
shutdown /h