BeforeAll {
    . "$PSScriptRoot/Clear-StaleWorkspaceTemp.ps1"

    # 创建文件并把修改时间设为 $AgeDays 天前
    function New-DatedFile {
        param(
            [Parameter(Mandatory)][string]$Path,
            [Parameter(Mandatory)][int]$AgeDays
        )

        New-Item -ItemType File -Path $Path -Force | Out-Null
        (Get-Item -LiteralPath $Path).LastWriteTime = (Get-Date).AddDays(-$AgeDays)
    }

    # 把目录本身及其全部后代统一设为 $AgeDays 天前。
    # 必须先设后代再设目录，否则设置子项会刷新目录自身的 LastWriteTime。
    function Set-TreeAge {
        param(
            [Parameter(Mandatory)][string]$Path,
            [Parameter(Mandatory)][int]$AgeDays
        )

        $timestamp = (Get-Date).AddDays(-$AgeDays)
        foreach ($child in Get-ChildItem -LiteralPath $Path -Recurse -Force) {
            $child.LastWriteTime = $timestamp
        }
        (Get-Item -LiteralPath $Path).LastWriteTime = $timestamp
    }
}

Describe 'Clear-StaleWorkspaceTemp' {
    BeforeEach {
        $script:root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $script:root | Out-Null

        # 测试用回收动作直接删除，避免把测试临时文件丢进用户回收站
        $script:removeItem = { param($Item) Remove-Item -LiteralPath $Item.FullName -Recurse -Force }

        $script:workspace = Join-Path $script:root 'ws'
        New-Item -ItemType Directory -Path $script:workspace | Out-Null
    }

    It '回收整体超过 30 天未修改的条目，保留新条目' {
        $oldDir = Join-Path $script:workspace '.trash/old-task'
        New-Item -ItemType Directory -Path $oldDir | Out-Null
        New-DatedFile -Path (Join-Path $oldDir 'a.txt') -AgeDays 40
        Set-TreeAge -Path $oldDir -AgeDays 40

        $newDir = Join-Path $script:workspace '.trash/new-task'
        New-Item -ItemType Directory -Path $newDir | Out-Null
        New-DatedFile -Path (Join-Path $newDir 'a.txt') -AgeDays 1

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 1
        $result[0].FullName | Should -Be $oldDir
        Test-Path -LiteralPath $oldDir | Should -BeFalse
        Test-Path -LiteralPath $newDir | Should -BeTrue
    }

    It '目录本身很旧但后代刚修改过时不回收' {
        $dir = Join-Path $script:workspace '.scratch/session'
        New-Item -ItemType Directory -Path $dir | Out-Null
        $modified = Join-Path $dir 'recent.txt'
        New-DatedFile -Path $modified -AgeDays 2
        # 只把目录时间打旧，模拟"上层目录很旧、内容仍在使用"
        (Get-Item -LiteralPath $dir).LastWriteTime = (Get-Date).AddDays(-60)

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 0
        Test-Path -LiteralPath $dir | Should -BeTrue
        Test-Path -LiteralPath $modified | Should -BeTrue
    }

    It '同时处理 .trash 与 .scratch 的顶层文件' {
        New-Item -ItemType Directory -Path (Join-Path $script:workspace '.trash') | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:workspace '.scratch') | Out-Null
        $trashFile = Join-Path $script:workspace '.trash/old.txt'
        $scratchFile = Join-Path $script:workspace '.scratch/old.log'
        New-DatedFile -Path $trashFile -AgeDays 45
        New-DatedFile -Path $scratchFile -AgeDays 45

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 2
        Test-Path -LiteralPath $trashFile | Should -BeFalse
        Test-Path -LiteralPath $scratchFile | Should -BeFalse
    }

    It '保留未到期的内容' {
        $dir = Join-Path $script:workspace '.scratch/recent'
        New-Item -ItemType Directory -Path $dir | Out-Null
        New-DatedFile -Path (Join-Path $dir 'a.txt') -AgeDays 29
        Set-TreeAge -Path $dir -AgeDays 29

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 0
        Test-Path -LiteralPath $dir | Should -BeTrue
    }

    It '不处理工作区更深层的 .scratch' {
        $nested = Join-Path $script:workspace 'nested'
        $nestedTemp = Join-Path $nested '.scratch/old'
        New-Item -ItemType Directory -Path $nestedTemp | Out-Null
        New-DatedFile -Path (Join-Path $nestedTemp 'a.txt') -AgeDays 90
        Set-TreeAge -Path $nestedTemp -AgeDays 90

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 0
        Test-Path -LiteralPath $nestedTemp | Should -BeTrue
    }

    It '不跟随联接点：按目录自身时间判定，且链接目标保持不动' {
        $outside = Join-Path $TestDrive 'outside'
        New-Item -ItemType Directory -Path $outside | Out-Null
        $outsideFile = Join-Path $outside 'recent.txt'
        New-DatedFile -Path $outsideFile -AgeDays 1

        # 目录整体 60 天未动，但里面有一个刚创建的联接点指向外部活跃目录
        $dir = Join-Path $script:workspace '.scratch/link-holder'
        New-Item -ItemType Directory -Path $dir | Out-Null
        New-Item -ItemType Junction -Path (Join-Path $dir 'to-outside') -Target $outside | Out-Null
        (Get-Item -LiteralPath $dir).LastWriteTime = (Get-Date).AddDays(-60)

        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        # 联接点自身的时间不参与判定，因此该条目仍算陈旧
        $result | Should -HaveCount 1
        $result[0].FullName | Should -Be $dir
        Test-Path -LiteralPath $dir | Should -BeFalse
        Test-Path -LiteralPath $outsideFile | Should -BeTrue
    }

    It '工作区没有临时目录时返回空且不报错' {
        $result = @(Clear-StaleWorkspaceTemp -RootDirectory $script:root -MinimumAgeDays 30 -RemoveItem $script:removeItem)

        $result | Should -HaveCount 0
    }

    It '根目录不存在时抛错' {
        $missing = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))

        { Clear-StaleWorkspaceTemp -RootDirectory $missing -MinimumAgeDays 30 -RemoveItem $script:removeItem } |
            Should -Throw
    }
}
