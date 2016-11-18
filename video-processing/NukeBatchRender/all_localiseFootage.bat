@ECHO OFF
SET "serverZ=%~1"
IF NOT EXIST "%~1" (
    SET "serverZ=\\192.168.1.4\f"
)
FOR %%i in ("%~dp0\*.nk") do (
	ECHO.
	ECHO %%~ni
	ECHO.
	CALL "%~dp0\localiseFootage.bat" "%%~i" "%serverZ%"
)
ECHO ----------------
ECHO È«²¿ËØ²Ä»º´æÍê±Ï
ECHO ----------------
IF NOT EXIST "%~1" (
    PAUSE
)