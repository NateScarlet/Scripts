reg add HKCU\Software\Classes\screenshot /f /v "URL Protocol"
reg add HKCU\Software\Classes\screenshot\shell\open\command /f /d "\"C:\Program Files\ShareX\ShareX.exe\" -RectangleRegion"
