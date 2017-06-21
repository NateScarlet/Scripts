@ECHO off
SET "TEXT=nuke.pluginAddPath('//Server/scripts/NukePlugins')"
SET "FILE=%UserProfile%\.nuke\init.py"

FIND /C /I "%TEXT%" "%FILE%" >nul 2>nul
IF %ERRORLEVEL% NEQ 0 ECHO.>>"%FILE%" && ECHO %TEXT%>>"%FILE%"

START "" notepad.exe  "%FILE%"
ECHO 现在重开Nuke插件应该已经安装好了
PAUSE