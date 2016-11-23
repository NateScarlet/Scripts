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
	WinWait, NXN alienbrain ahk_exe NxNManagerClient.exe, , 3
	Send, {SPACE}
	WinWait, NXN alienbrain Manager Client ahk_exe NxNManagerClient.exe, , 3
	WinMaximize
}
IfWinExist, ahk_class QWidget ahk_exe Nuke10.0.exe, , Hiero
{
	WinActivate
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
Run, %Windir%\explorer.exe
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