# 回收 C:\Workspaces 下各工作区 .trash / .scratch 中超过 30 天未修改的内容。
# 错误直接抛给调用方（Invoke-DailyTask 会统一通知），此处不再重复捕获。
$ErrorActionPreference = 'Stop'

. "$PSScriptRoot/../lib/Send-To-RecycleBin.ps1"
. "$PSScriptRoot/../lib/Clear-StaleWorkspaceTemp.ps1"

Write-Host '扫描各工作区 .trash / .scratch（超过 30 天未修改的内容）...' -ForegroundColor Cyan

$removed = Clear-StaleWorkspaceTemp -RootDirectory 'C:\Workspaces' -MinimumAgeDays 30 -RemoveItem {
    param($Item)
    # 逐项输出，避免长时间静默看起来像卡死
    Write-Host "  回收: $($Item.FullName)" -ForegroundColor Yellow
    Send-To-RecycleBin $Item
}

Write-Host "已回收 $($removed.Count) 项超过 30 天未修改的工作区临时内容" -ForegroundColor Cyan
