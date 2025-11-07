#Requires AutoHotkey v2.0
#Warn All
#SingleInstance Force
SendMode "Input"
SetWorkingDir A_ScriptDir

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
        Run A_Programs "\Google Chrome.lnk"
    }
}

; 2. 启动 Obsidian
$#2:: {
    create() {
        Run A_Programs "\Obsidian.lnk"
    }

    CycleWindows("ahk_exe Obsidian.exe", create)
}

; 3. VS Code 窗口循环切换
$#3:: {
    create() {
        Run "code"
    }

    CycleWindows("ahk_exe Code.exe", create)
}

; 4. 启动 Everything
$#f:: Run A_ProgramFiles "\Everything\Everything.exe"

; 5. 资源管理器窗口循环切换
$#e:: {
    create() {
        Run A_WinDir "\explorer.exe"
        Run A_WinDir "\explorer.exe"
    }

    CycleWindows("ahk_class CabinetWClass ahk_exe explorer.exe", create)
}

; 6. ConEmu 终端切换
~!^t:: {
    if WinExist("ahk_exe WindowsTerminal.exe") {
        WinActivate
    } else {
        Run "wt"
    }
}
