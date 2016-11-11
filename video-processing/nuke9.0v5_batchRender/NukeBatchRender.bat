@ECHO off
SETLOCAL enabledelayedexpansion
FOR %%i in ("%~dp0\*.nk") do (
	ECHO.
	ECHO %%~ni
	SET startTime=!time:~0,8!
	ECHO.
	"C:\Program Files\Nuke9.0v5\Nuke9.0.exe" -x -f --cont "%%~i" 2>>Renderlog.txt
	SET finishTime=!time:~0,8!
	ECHO !date! !startTime! !finishTime!	%%~ni >>Renderlog.txt
)
ECHO !time:~0,8! äÖÈ¾Íê³É
START RenderLog.txt
EXIT