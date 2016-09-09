SET UserDir=%UserProfile%\.nuke
FOR %%i in (ToolSets,NodePresets) do (
XCOPY /E /Y "%UserDir%\%%i" "%UserDir%\bak\%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%\%%i\"
XCOPY /E /Y "%UserDir%\%%i" "%~dp0\%%i\"
RMDIR /S /Q "%UserDir%\%%i"
MKLINK /J "%UserDir%\%%i" "%~dp0%%i"
)
::PAUSE