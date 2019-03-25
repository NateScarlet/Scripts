;

$#f:: Run Everything

$#1:: 
IfWinExist, ahk_exe chrome.exe
{
	WinActivate
}
else
{
	Run Chrome
}
return

$#2:: 
IfWinNotExist, ahk_exe CgTeamWork.exe
	{
	Run, CGTeamWork 
	}
GroupAdd, G_WORK, ahk_class QWidget ahk_exe Nuke10.0.exe, , , Hiero
GroupAdd, G_WORK, ahk_class QWidget ahk_exe Nuke10.5.exe, , , Hiero
GroupAdd, G_WORK, ahk_class Qt5QWindowIcon ahk_exe CgTeamWork.exe
GroupActivate, G_WORK
return

$#3:: 
IfWinExist, ahk_exe code.exe 
{
	GroupAdd, G_CODE, ahk_exe code.exe
	GroupActivate, G_CODE
}
else
	Run, code
return

$!^t::
IfWinExist, ahk_exe ConEmu64.exe
	WinActivate
else
	Run, ConEmu64.exe
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
