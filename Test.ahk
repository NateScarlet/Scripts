#SingleInstance force
#NoEnv
确保管理员权限:
if not A_IsAdmin
{
   Run *RunAs "%A_ScriptFullPath%"  ; 需要 v1.0.92.01+
   ExitApp
}

Run "firefox"-url imacros://run/?m=TabClose.iim

ExitApp

$esc::ExitApp