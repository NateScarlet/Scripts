# 递归枚举后代的选项：跳过符号链接/联接点（不跟随到工作区外，也不把链接目标的时间算进来），
# 隐藏文件照常统计（默认会跳过 Hidden/System），无权限时直接抛错而不是当作空目录。
$script:DescendantEnumeration = [System.IO.EnumerationOptions]@{
    RecurseSubdirectories = $true
    AttributesToSkip      = [System.IO.FileAttributes]::ReparsePoint
    IgnoreInaccessible    = $false
}

# 返回条目自身及其所有后代的最后修改时间（取最大值）。
#
# 目录的 LastWriteTime 只随直接子项的增删更新，孙辈被修改时不会变化；
# 只按目录自身时间判定会把仍在使用的临时目录当成陈旧内容。
function Get-NewestWriteTime {
    param(
        [Parameter(Mandatory)]
        [System.IO.FileSystemInfo]$Item
    )

    $newest = $Item.LastWriteTime
    # 不跟随符号链接/联接点，避免统计越出工作区
    if ($Item -isnot [System.IO.DirectoryInfo] -or ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        return $newest
    }

    # 用 .NET 一次性递归枚举：Get-ChildItem 每层都走一遍 PowerShell 对象管线，
    # 同一棵 37 万文件的树要 189 秒，这里是 9 秒
    foreach ($descendant in $Item.EnumerateFileSystemInfos('*', $script:DescendantEnumeration)) {
        if ($descendant.LastWriteTime -gt $newest) {
            $newest = $descendant.LastWriteTime
        }
    }
    return $newest
}

# 清理各工作区 .trash 与 .scratch 中整体超过指定天数未修改的条目。
#
# RootDirectory 的直接子目录被视为一个工作区，只处理工作区根下的 .trash/.scratch，
# 其直接子项是回收单位：只有该子项与其全部后代都早于截止时间才会被交给 RemoveItem，
# 因此仍在使用中的临时目录（哪怕上层目录很旧）不会被带走。
function Clear-StaleWorkspaceTemp {
    <#
    .SYNOPSIS
        回收各工作区 .trash / .scratch 中超过指定天数未修改的内容。

    .PARAMETER RootDirectory
        工作区根目录，其直接子目录被视为工作区。

    .PARAMETER MinimumAgeDays
        条目的最后修改时间早于该天数才回收。

    .PARAMETER RemoveItem
        回收单个条目的动作，由调用方注入（生产环境为发送到回收站）。

    .OUTPUTS
        被交给 RemoveItem 的条目。
    #>
    param(
        [Parameter(Mandatory)]
        [string]$RootDirectory,

        [Parameter(Mandatory)]
        [ValidateRange(1, 3650)]
        [int]$MinimumAgeDays,

        [Parameter(Mandatory)]
        [scriptblock]$RemoveItem
    )

    if (-not (Test-Path -LiteralPath $RootDirectory -PathType Container)) {
        throw "工作区根目录不存在: $RootDirectory"
    }

    $cutoff = (Get-Date).AddDays(-$MinimumAgeDays)
    $removed = [System.Collections.Generic.List[System.IO.FileSystemInfo]]::new()

    # 只枚举直接子目录：更深的 .scratch 属于别的项目或依赖，不在本脚本职责内
    foreach ($workspace in Get-ChildItem -LiteralPath $RootDirectory -Directory -Force) {
        foreach ($tempName in @('.trash', '.scratch')) {
            $tempDirectory = Join-Path $workspace.FullName $tempName
            if (-not (Test-Path -LiteralPath $tempDirectory -PathType Container)) {
                continue
            }

            foreach ($entry in Get-ChildItem -LiteralPath $tempDirectory -Force) {
                if ((Get-NewestWriteTime -Item $entry) -lt $cutoff) {
                    & $RemoveItem $entry
                    $removed.Add($entry)
                }
            }
        }
    }

    return $removed.ToArray()
}
