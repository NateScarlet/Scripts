$folder = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path
function Move-To-RecycleBin {
    param([string] $Path)

    $shell = New-Object -ComObject 'Shell.Application'

    $shell.NameSpace(0).
    ParseName($Path).
    InvokeVerb('Delete')
}

Get-ChildItem $folder | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } | ForEach-Object { Move-To-RecycleBin $_ }
