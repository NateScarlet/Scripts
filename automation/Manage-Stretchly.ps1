# 脚本用途：根据当前会话状态自动管理 Stretchly
# 1. 活跃的远程会话 (Active RDP) -> 暂停 Stretchly 休息提醒
# 2. 已断开的远程会话或本地会话 -> 恢复 Stretchly 休息提醒

param(
    [Parameter(Mandatory = $false)]
    [bool]$IsRemote
)

# 如果没有传入参数，则主动获取会话状态
if (-not $PSBoundParameters.ContainsKey('IsRemote')) {
    . "$PSScriptRoot\..\lib\Get-SessionStatus.ps1"
    $IsRemote = Get-IsRemoteSession
}

$stretchlyExe = "$env:LOCALAPPDATA\Programs\Stretchly\Stretchly.exe"
if (-not (Test-Path $stretchlyExe)) {
    exit 0
}

# 检查 Stretchly 进程是否已经在运行
$process = Get-Process Stretchly -ErrorAction SilentlyContinue

if ($IsRemote) {
    # 远程会话：暂停休息提醒
    # 使用 Start-Process 异步执行命令，避免在 Stretchly 刚启动时脚本发生阻塞
    Start-Process $stretchlyexe -ArgumentList "pause"
    if ($process) {
        Write-Host "⏸️ 已在远程会话中暂停 Stretchly 休息提醒"
    }
    else {
        # 如果当前未运行，上述命令会启动它并处于暂停状态
        Write-Host "🚀 Stretchly 未运行，已启动并暂停休息提醒"
    }
}
else {
    # 本地会话：恢复休息提醒
    if ($process) {
        Start-Process $stretchlyexe -ArgumentList "resume"
        Write-Host "▶️ 已在本地会话中恢复 Stretchly 休息提醒"
    }
    else {
        # 如果未运行且是本地会话，直接启动主程序即可（默认即为恢复/运行状态）
        Start-Process $stretchlyexe
        Write-Host "🚀 Stretchly 未运行，已启动程序"
    }
}
