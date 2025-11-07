. "$PSScriptRoot/../lib/Send-To-RecycleBin.ps1"


Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/output" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | ForEach-Object { Send-To-RecycleBin $_ }
Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/input" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Send-To-RecycleBin $_ }
Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/user/default/workflows" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Send-To-RecycleBin $_ }
