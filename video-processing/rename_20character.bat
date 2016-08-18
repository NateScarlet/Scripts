@echo off
setlocal ENABLEDELAYEDEXPANSION
for /f "delims=" %%i in ('dir /s /b %~dp0') do (
	set rawName=%%~ni
	ren %%~nxi !rawName:~0,19!%%~xi
)