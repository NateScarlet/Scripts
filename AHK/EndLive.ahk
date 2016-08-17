#NoEnv
确保管理员权限:
if not A_IsAdmin
{
   Run *RunAs "%A_ScriptFullPath%"  ; 需要 v1.0.92.01+
   ExitApp
}
Sendmode event

BlockInput, On

Run "firefox" -new-window imacros://run/?m=live.bilibili`%5CEndLive.iim
WinWaitActive, iMacros ahk_class MozillaDialogClass
Send {ENTER}
WinClose OBS ahk_exe obs64.exe
WinActivate 退出OBS?, , 2
WinWaitActive 退出OBS?, , 2
If (ErrorLevel = 0) 
	Send {Enter}

BlockInput, Off
ExitApp

$Esc::ExitApp