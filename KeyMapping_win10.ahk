#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.


$#1:: 
IfWinExist, ahk_exe firefox.exe
{
	WinActivate
}
else
{
	Run firefox
}
return

$#2:: 
Run PS
return

$#3:: 
IfWinExist, ahk_exe EmEditor.exe
{
	WinActivate
}
else
{
	Run txt
}
return

$#f:: 
Run, Everything
return

$^#e:: 
IfWinExist, ahk_exe Q-Dir.exe
{
	WinActivate
}
else
{
	Run Q-Dir
}
return