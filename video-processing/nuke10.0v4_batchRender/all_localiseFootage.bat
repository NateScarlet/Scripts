@ECHO off
FOR %%i in ("%~dp0\*.nk") do (
	ECHO.
	ECHO %%~ni
	ECHO.
	"%~dp0\localiseFootage.bat" "%%~i" 
)
ECHO Íê³É
PAUSE