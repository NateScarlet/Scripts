$shell = New-Object -ComObject 'Shell.Application'

function Move-To-RecycleBin {
    param([string] $Path)

    $Path


    $shell.NameSpace(0).
    ParseName($Path).
    InvokeVerb('Delete')
}

Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/output" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | ForEach-Object { Move-To-RecycleBin $_ }
Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/input" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Move-To-RecycleBin $_ }
Get-ChildItem -Recurse "C:/ComfyUI/ComfyUI/user/default/workflows" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Move-To-RecycleBin $_ }
