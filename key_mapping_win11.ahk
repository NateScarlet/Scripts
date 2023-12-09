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

~F2::
; https://www.autohotkey.com/docs/commands/SoundSet.htm#Soundcard
mic_device:=11
SoundGet,mic_mute,,Mute,%mic_device%
if ErrorLevel 
{
	TrayTip, 获取麦克风失败, %ErrorLevel%, , 0x3
	SoundPlay, %A_WinDir%\Media\Windows Error.wav
	return
}
if mic_mute=On
{
	SoundSet, 0,,Mute,%mic_device%
	SoundSet, 100,,Volume,%mic_device%
	SoundPlay, %A_WinDir%\Media\Speech On.wav
} 
else
{
	SoundSet, 1,,Mute,%mic_device%
	SoundPlay, %A_WinDir%\Media\Speech Off.wav
}
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
