#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

Sleep, 60000

ToDir("X:")
ToDir("Y:")
ToDir("Z:")
ExitApp

;~ 路径是大小写敏感的
ToDir(dir)
{

	Run, explorer.exe %dir%
	WinWaitActive, ahk_exe explorer.exe, 地址: %dir%
	Sleep, 0
	WinClose,
}

