;

Shortcut = %UserProfile%\Shortcut


Loop {
	PrevWin := CurrentWin
    WinGet, CurrentWin, ID, A
	If (CurrentWin != PrevWin) {
	    OnWinChange()
	}
}

OnWinChange()
{
    IfWinExist, ahk_exe WerFault.exe,
		sleep, 3000
        WinClose,
	IfWinExist, ahk_exe CrashReporterNuke.exe,
		WinClose,
}

$#f:: Run %Shortcut%\Everything

$#1:: 
IfWinExist, ahk_exe chrome.exe
{
	WinActivate
}
else
{
	Run %Shortcut%\Chrome
}
return

$#2:: 
IfWinNotExist, ahk_exe CgTeamWork.exe
	{
	Run, CGTeamWork 
	}
GroupAdd, G_WORK, ahk_class QWidget ahk_exe Nuke10.0.exe, , , Hiero
GroupAdd, G_WORK, ahk_class Qt5QWindowIcon ahk_exe CgTeamWork.exe
GroupActivate, G_WORK
return

$^#2:: 
IfWinNotExist, ahk_exe NxNManagerClient.exe
{
	Run, %Shortcut%\NxN
	WinWait, ahk_class #32770 ahk_exe NxNManagerClient.exe, , 3,
	WinClose,
	WinWaitActive, NXN alienbrain Manager Client ahk_exe NxNManagerClient.exe, , 3,
	WinMaximize
}
else
{
	WinActivate, ahk_class ATL:0046DEB0 ahk_exe NxNManagerClient.exe
}
return

$#3:: 
IfWinExist, ahk_exe Typora.exe 
{
	GroupAdd, G_TYPORA, ahk_exe Typora.exe
	GroupActivate, G_TYPORA
}
else
    Run, "%USERPROFILE%\Shortcut\txt.lnk"
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
	Run %Shortcut%\Q-Dir
}
return
