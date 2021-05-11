reg add HKCU\Software\Classes\screenshot /f /v "URL Protocol"
reg add HKCU\Software\Classes\screenshot\shell\open\command /f /d "\"%WinDir%\System32\SnippingTool.exe\""
