;~ 在下方设置账号及账号区域

account1 = 343571205@qq.com
region1 = 亚洲
account2 = NateScarlet@Gmail.com
region2 = 中国大陆
passwordNotSame = 0 ;如果两个账号密码不一样则改为1

;~ 使用前确认 战网客户端可以登录外服
;~ 使用前确认 开启允许多个战网进程


#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.
CoordMode, Mouse, Client

;~ 关闭已有BN进程
Loop
{
   Process, Exist, Battle.net.exe
   if (ErrorLevel = 0)
      break
   Process, Close, %ErrorLevel%
}

;~ 手动输入密码登录战网
text := account1 "`n" region1
InputBox, password, 输入密码, %text%, HIDE, , 150, , , , , %password%
LogIn(account1, password, region1)
WinWait, ahk_exe Battle.net.exe
WinGet, temp_hwnd
WinMove, , , 0, 0, % A_ScreenWidth / 2, % A_ScreenHeight
If passwordNotSame
{
   text := account2 "`n" region2
   InputBox, password, 输入密码, %text%, HIDE, , 130, , , , , %password%
}
LogIn(account2, password, region2)
WinWaitNotActive, ahk_id %temp_hwnd%
WinMove, ahk_exe Battle.net.exe, , % A_ScreenWidth / 2, 0 , % A_ScreenWidth / 2, % A_ScreenHeight , ahk_id %temp_hwnd%

ExitApp

$esc::ExitApp

;~ 手动输入验证码
VerificationIf()
{
   IfWinExist, 战网登录 ahk_exe Battle.net.exe
   {  
      WinGetPos, , , w, h, 战网登录
      if (h=501 or h = 576)   
      {
         InputBox, code, 输入验证码, , , , 130
         offset := w - 363
         x := 178 + offset
         Click, %x%, 365
         Send, %code%
      }
   }
}

;~ 自动重试连接
RetryIf()
{
   waitTime = 0
   Loop
   {
      Sleep, %waitTime%
      Sleep, 1000
      WinGetPos, , , w, h, 战网登录 
      If (h = 496)
      {
         offset := w - 363
         x := 111 + offset
         Click, %x%, 453
         WinWaitActive
         waitTime += 200
         continue
      }
      break
   }
}

;~ 登录
LogIn(UserName, Password, Region)
{
   ;~ 运行战网
   Run, Batte.net.lnk
   WinWait, 战网登录 ahk_exe Battle.net.exe
   Sleep, 0
   Sleep, 500
   ;~ 选择战网区域
   WinGetPos, , , w
   offset := w - 363
   x := 60 + offset
   Click, %x%, 120
   Sleep, 0
   Sleep, 1000
   x := 100 + offset
   if (Region = "北美洲")
      Click,  %x%, 160
   if (Region = "殴洲")
      Click,  %x%, 180   
   if (Region = "亚洲")
      Click,  %x%, 200
   if (Region = "中国大陆")
      Click,  %x%, 220
   Sleep, 0
   WinWaitActive
   WinGetPos, , , w
   offset := w - 363
   RetryIf()
   Sleep, 0
   WinActivate, 战网登录 ahk_exe Battle.net.exe
   WinWaitActive
   ;~ 输入账号密码
   x := 180 + offset   
   Click, %x%, 170
   Send, ^a
   Send, %UserName%
   Send, ^a
   Send, {Tab}
   Sleep, 0
   Sleep, 1000
   Send, %Password%
   ;~ 等待载入
   Loop
   {
      PixelGetColor, temp_color, 80, 290
      If (temp_color != "0x2C221D")
         break
      Sleep, 200
   }
   ;~ 确认登录
   VerificationIf()
   Send, {Enter}
   WinWaitClose, , , 10
   if (ErrorLevel = 1)
   {
      MsgBox, 本次未能成功登录
      ExitApp
   }
}