MKDIR "%~dp0Archived_Files" 2>nul
FORFILES /P "%~dp0" /S /D -60 /C "CMD /C MOVE ^"@path^" ^"%~dp0Archived_Files\@relpath^"" 
PAUSE