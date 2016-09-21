#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

Sleep, 60000
ToDir("x:")
ToDir("y:")
ToDir("z:")
Sleep, 1000
Send, !{F4 3}
ExitApp

ToDir(dir)
{
	Run, explorer.exe %dir%
}

