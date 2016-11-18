@ECHO off
FOR %%i in ("%~dp0\*.nk") do (
	ECHO.
	ECHO %%~ni
	ECHO.
	"%~dp0\localiseFootage.bat" "%%~i" "\\192.168.1.4\f"
)
ECHO Íê³É
PAUSE