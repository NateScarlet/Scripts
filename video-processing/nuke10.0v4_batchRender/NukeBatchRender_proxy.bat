@ECHO off
SETLOCAL enabledelayedexpansion
FOR %%i in ("%~dp0\*.nk") do (
	ECHO.
	ECHO %%~ni
	SET startTime=!time:~0,8!
	ECHO.
	nuke10.0.exe -x -p "%%~i" 
	SET finishTime=!time:~0,8!
	ECHO !date! !startTime! !finishTime!	%%~ni^(����ģʽ^) >>Renderlog.txt
)
ECHO !time:~0,8! ��Ⱦ���
START RenderLog.txt
::SHUTDOWN /h