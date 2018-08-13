; #NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

#SingleInstance force

; Loop
; {
	; IfWinActive, ahk_exe tldenoise5_x64.exe
		; WinMinimize
	; PrevWin := CurrentWin
    ; WinGet, CurrentWin, ID, A
	; If (CurrentWin != PrevWin) {
	    ; OnWinChange()
	; }
; }

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
;~ Run, XnView
return

$#3:: 
IfWinNotExist, ahk_exe notepad++.exe
{
    Run, "%USERPROFILE%\Shortcut\txt.lnk"
}

GroupAdd, G_TXT, ahk_exe notepad++.exe
GroupAdd, G_TXT, ahk_exe Typora.exe
GroupActivate, G_TXT

return

$#f:: 
Run, "%USERPROFILE%\Shortcut\Everything.lnk"
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

^!t::
Run, posh
return

; LButton::Send, % "{" (A_TimeSincePriorHotkey > 50 ? A_ThisHotkey " Down" : "") "}"
; LButton Up::Send, {%A_ThisHotkey%}