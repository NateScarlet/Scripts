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

if ($IsRemote) {
    # 远程会话：暂停休息提醒
    & $stretchlyExe pause
    Write-Host "⏸️ 已在远程会话中暂停 Stretchly 休息提醒"
}
else {
    # 本地会话：恢复休息提醒
    & $stretchlyExe resume
    Write-Host "▶️ 已在本地会话中恢复 Stretchly 休息提醒"
}
