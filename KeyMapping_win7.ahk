Loop {
    IfWinExist, ahk_exe WerFault.exe,
        WinClose,
	IfWinExist, ahk_exe CrashReporterNuke.exe,
		WinClose,
}

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
IfWinNotExist, ahk_exe NxNManagerClient.exe
{
	Run, NxN
	WinWait, ahk_class #32770 ahk_exe NxNManagerClient.exe, , 3,
	WinClose,
	WinWaitActive, NXN alienbrain Manager Client ahk_exe NxNManagerClient.exe, , 3,
	WinMaximize
}
IfWinExist, ahk_class QWidget ahk_exe Nuke10.0.exe, , Hiero
{
	GroupAdd, G_NUKE, ahk_class QWidget ahk_exe Nuke10.0.exe, , , Hiero
	GroupActivate, G_NUKE
}
else
{
	WinActivate, ahk_class ATL:0046DEB0 ahk_exe NxNManagerClient.exe
}
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



$#Tab::
Run, Dexpot