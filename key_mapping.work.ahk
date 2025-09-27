#Requires AutoHotkey v2.0
#Warn All
#SingleInstance Force
SendMode "Input"
SetWorkingDir A_ScriptDir

; 获取用户目录
userProfile := EnvGet("UserProfile")

; 通用窗口循环函数
CycleWindows(winTitle, createAction := unset) {
    ; 获取所有匹配窗口
    windows := WinGetList(winTitle)
    
    if (windows.Length = 0) {
        ; 没有窗口时执行创建操作（如果提供了）
        if IsSet(createAction) {
            createAction()
        }
        return
    }
    
    ; 获取当前活动窗口
    currentHwnd := WinActive("A")
    
    ; 查找当前活动窗口在列表中的位置
    currentIndex := 0
    for i, hwnd in windows {
        if (hwnd = currentHwnd) {
            currentIndex := i
            break
        }
    }
    
    ; 计算下一个要激活的窗口索引
    nextIndex := currentIndex + 1
    if (nextIndex > windows.Length) {
        nextIndex := 1
    }
    
    ; 激活下一个窗口
    WinActivate windows[nextIndex]
}

; 1. Chrome 窗口切换
$#1:: {
    if WinExist("ahk_exe chrome.exe") {
        WinActivate
    } else {
        Run "chrome"
    }
}

; 2. CGTeamWork 和相关应用窗口管理
$#2:: {
    ; 如果 CGTeamWork 不存在则启动
    if !WinExist("ahk_exe CgTeamWork.exe") {
        Run "CGTeamWork"
    }
    
    ; 定义工作窗口组
    workWindows := []
    
    ; 添加符合条件的窗口
    for hwnd in WinGetList() {
        exeName := WinGetProcessName(hwnd)
        winClass := WinGetClass(hwnd)
        
        ; Nuke 10.0
        if (exeName = "Nuke10.0.exe" && winClass = "QWidget") {
            workWindows.Push(hwnd)
        }
        ; Nuke 10.5
        else if (exeName = "Nuke10.5.exe" && winClass = "QWidget") {
            workWindows.Push(hwnd)
        }
        ; CGTeamWork
        else if (exeName = "CgTeamWork.exe" && winClass = "Qt5QWindowIcon") {
            workWindows.Push(hwnd)
        }
    }
    
    ; 如果没有找到窗口，直接返回
    if (workWindows.Length = 0) {
        return
    }
    
    ; 获取当前活动窗口
    currentHwnd := WinActive("A")
    
    ; 查找当前活动窗口在列表中的位置
    currentIndex := 0
    for i, hwnd in workWindows {
        if (hwnd = currentHwnd) {
            currentIndex := i
            break
        }
    }
    
    ; 计算下一个要激活的窗口索引
    nextIndex := currentIndex + 1
    if (nextIndex > workWindows.Length) {
        nextIndex := 1
    }
    
    ; 激活下一个窗口
    WinActivate workWindows[nextIndex]
}

; 3. VS Code 窗口循环切换
$#3:: {
    ; 定义创建操作：启动一个 VS Code 实例
    createVSCode() {
        Run "code"
    }
    
    CycleWindows("ahk_exe Code.exe", createVSCode)
}

; 4. 启动 Everything
$#f:: Run A_ProgramFiles "\Everything\Everything.exe"

; 5. 资源管理器窗口循环切换
$#e:: {
    ; 定义创建操作：启动两个资源管理器实例
    createExplorers() {
        Run A_WinDir "\explorer.exe"
        Run A_WinDir "\explorer.exe"
    }
    
    CycleWindows("ahk_class CabinetWClass ahk_exe explorer.exe", createExplorers)
}

; 6. ConEmu 终端切换
~!^t:: {
    if WinExist("ahk_exe WindowsTerminal.exe") {
        WinActivate
    } else {
        Run "wt"
    }
}
