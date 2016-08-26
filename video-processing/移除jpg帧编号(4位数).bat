@echo off
setlocal ENABLEDELAYEDEXPANSION
for /f "delims=" %%i in ('dir /s /b %~dp0\*.jpg') do (
	set rawName=%%~ni
	ren "%%~nxi" "!rawName:~0,-5!%%~xi"
)
ENDLOCAL