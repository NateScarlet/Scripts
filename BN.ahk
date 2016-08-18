﻿#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.
;~ if not A_IsAdmin ;确保管理员权限
;~ {
   ;~ Run *RunAs "%A_ScriptFullPath%"  ; 需要 v1.0.92.01+
   ;~ ExitApp
;~ }
CoordMode, Mouse, Client

;~ 关闭已有BN进程
Loop
{
   Process, Exist, Battle.net.exe
   if (ErrorLevel = 0)
      break
   Process, Close, %ErrorLevel%
}

;~ 登录
VerificationIf()
{
   IfWinExist, 战网登录 ahk_exe Battle.net.exe
   {  
      WinGetPos, , , w, h, 战网登录
      if (h=501 or h = 576)   
      {
         InputBox, code, 输入验证码, , , , 130
         Click, 178, 365
         Send, %code%
      }
   }
}

RetryIf()
{
   waitTime = 0
   Loop ;连接不好的时候重试登录
   {
      Sleep, %waitTime%
      Sleep, 1000
      WinGetPos, , , w, h, 战网登录 
      If (h = 496)
      {
         Click, 111, 453
         WinWaitActive
         waitTime += 200
         continue
      }
      break
   }
}

LogIn(UserName, Password, Region)
{
   Run, Batte.net.lnk
   WinWait, 战网登录 ahk_exe Battle.net.exe
   Sleep, 0
   Sleep, 500
   Click, 49, 119
   Sleep, 0
   Sleep, 1000
   if (Region = "北美洲")
      Click, 100, 160
   if (Region = "殴洲")
      Click, 100, 180   
   if (Region = "亚洲")
      Click, 100, 200
   if (Region = "中国大陆")
      Click, 100, 220
   Sleep, 0
   WinWaitActive
   RetryIf()
   Sleep, 0
   WinActivate, 战网登录 ahk_exe Battle.net.exe
   WinWaitActive
   Click, 180, 170
   Send, ^a
   Send, %UserName%
   Send, ^a
   Send, {Tab}
   Sleep, 0
   Sleep, 1000
   Send, %Password%
   Loop ;等待载入
   {
      PixelGetColor, temp_color, 80, 290
      If (temp_color != "0x2C221D")
         break
      Sleep, 200
   }
   VerificationIf()
   Send, {Enter}
   WinWaitClose, , , 5
   if (ErrorLevel = 1)
   {
      MsgBox, 本次未能成功登录
      ExitApp
   }
}

InputBox, password, 输入密码, 台服, HIDE, , 130, , , , , %password%
LogIn("343571205@qq.com", password, "亚洲")
WinWait, ahk_exe Battle.net.exe
WinGet, temp_hwnd
WinMove, , , 0, 0, % A_ScreenWidth / 2, % A_ScreenHeight
;~ InputBox, password, 输入密码, 国服, HIDE, , 130, , , , , %password%
LogIn("NateScarlet@Gmail.com", password, "中国大陆")
WinWaitNotActive, ahk_id %temp_hwnd%
WinMove, ahk_exe Battle.net.exe, , % A_ScreenWidth / 2, 0 , % A_ScreenWidth / 2, % A_ScreenHeight , ahk_id %temp_hwnd%

ExitApp

$esc::ExitApp