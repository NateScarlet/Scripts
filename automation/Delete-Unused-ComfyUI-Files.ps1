. "$PSScriptRoot/../lib/Send-To-RecycleBin.ps1"
. "$PSScriptRoot/../lib/Send-Notification.ps1"

try {
    Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/output" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | ForEach-Object { Send-To-RecycleBin $_ }
    Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/input" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Send-To-RecycleBin $_ }
    Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/user/default/workflows" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Send-To-RecycleBin $_ }
}
catch {
    Write-Warning "执行出错: $_"
    Send-Notification -Title "Delete-Unused-ComfyUI-Files 出错" -Message $_.Exception.Message -Priority 8
}
