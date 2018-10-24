; #NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

#SingleInstance force

OnWinChange()
{
	WinWaitNotActive, ahk_exe NeptuniaReBirth2.exe
	{
        PostMessage, 0x06, 1, 0,
	}
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
    Run, "%LocalAppdata%\Programs\Microsoft VS Code\Code.exe"
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
	IfWinExist, ahk_exe doublecmd.exe
		WinActivate
	else
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
IfWinExist, ahk_exe ConEmu64.exe
	WinActivate
else
	Run, ConEmu64.exe
return

