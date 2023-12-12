#Warn  ; Enable warnings to assist with detecting common errors.
#NoEnv
#SingleInstance force
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

EnvGet, UserProfile, UserProfile

MouseState() {
	CoordMode, Mouse, Screen
	MouseGetPos, xpos, ypos
	return xpos ":" ypos
}


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
Run, Krita
return

$#3::
IfWinNotExist, ahk_exe code.exe
{
    Run, Code
}

GroupAdd, G_TXT, ahk_exe code.exe
GroupActivate, G_TXT

return

$#f::
Run, Everything
return

$#e::
IfWinNotExist, ahk_class CabinetWClass ahk_exe explorer.exe
{
	Run explorer.exe
	Run explorer.exe
}
else
{
	GroupAdd, G_EXLPORER, ahk_class CabinetWClass ahk_exe explorer.exe
	GroupActivate, G_EXPLORER
}
return

$!^t::
IfWinExist, ahk_exe WindowsTerminal.exe
	WinActivate
else
	Run, wt
return

+ScrollLock::
Winset, Alwaysontop, , A
return

!ScrollLock::
enable_state:=MouseState()
While, enable_state=MouseState() {
	Click
	Sleep 100
}
SoundPlay, %A_WinDir%\Media\Windows Print complete.wav
return
