; #NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

Loop
{
	IfWinActive, ahk_exe tldenoise5_x64.exe
		WinMinimize
	PrevWin := CurrentWin
    WinGet, CurrentWin, ID, A
	If (CurrentWin != PrevWin) {
	    OnWinChange()
	}
}

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
Run, PS
Run, XnView
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

$#e:: 
IfWinNotExist, ahk_class CabinetWClass ahk_exe explorer.exe
{
    Run, %Windir%\explorer.exe
	Run, %Windir%\explorer.exe
}
else
{
	GroupAdd, G_EXLPORER, ahk_class CabinetWClass ahk_exe explorer.exe
	GroupActivate, G_EXPLORER
}
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