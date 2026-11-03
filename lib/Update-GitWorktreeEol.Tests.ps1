BeforeAll {
    . "$PSScriptRoot/Update-GitWorktreeEol.ps1"
}

Describe 'Update-GitWorktreeEol' {
    BeforeEach {
        # 每个用例一个独立仓库，避免相互污染
        $script:repo = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $script:repo | Out-Null

        git -C $script:repo init --quiet --initial-branch=main
        if ($LASTEXITCODE -ne 0) { throw 'git init 失败' }

        [System.IO.File]::WriteAllText(
            (Join-Path $script:repo '.gitattributes'),
            "*.cmd text eol=crlf`n")
        [System.IO.File]::WriteAllText(
            (Join-Path $script:repo 'a.cmd'),
            "@echo off`r`necho hi`r`n")
        [System.IO.File]::WriteAllText(
            (Join-Path $script:repo 'b.ps1'),
            "Write-Host hi`n")

        git -C $script:repo add -A
        # 显式关闭签名，避免继承用户全局的 commit.gpgsign 配置
        git -C $script:repo -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false commit --quiet --no-gpg-sign -m init
        if ($LASTEXITCODE -ne 0) { throw 'git commit 失败' }
    }

    It '把 LF 行尾的 .cmd 重写为 CRLF' {
        $file = Join-Path $script:repo 'a.cmd'
        [System.IO.File]::WriteAllText($file, "@echo off`necho hi`n")

        Update-GitWorktreeEol -WorktreePath $script:repo -Pathspec '*.cmd' | Out-Null

        [System.IO.File]::ReadAllText($file) | Should -Be "@echo off`r`necho hi`r`n"
    }

    It '不触碰 pathspec 之外的文件' {
        $file = Join-Path $script:repo 'b.ps1'
        [System.IO.File]::WriteAllText($file, "Write-Host hi`n")
        $before = (Get-Item $file).LastWriteTimeUtc

        Update-GitWorktreeEol -WorktreePath $script:repo -Pathspec '*.cmd' | Out-Null

        [System.IO.File]::ReadAllText($file) | Should -Be "Write-Host hi`n"
        (Get-Item $file).LastWriteTimeUtc | Should -Be $before
    }

    It '索引 stat 与 LF 文件一致（git 判定干净）时也能修正行尾' {
        # 复现生产环境：文件在 .gitattributes 生效之前就以 LF 提交，
        # 索引记录的 stat 与磁盘上的 LF 文件一致，git 认为无需重写。
        $repo = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $repo | Out-Null
        git -C $repo init --quiet --initial-branch=main

        $file = Join-Path $repo 'legacy.cmd'
        [System.IO.File]::WriteAllText($file, "@echo off`necho hi`n")
        git -C $repo add -A
        git -C $repo -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false commit --quiet --no-gpg-sign -m legacy

        # 之后才加入 eol 规则
        [System.IO.File]::WriteAllText((Join-Path $repo '.gitattributes'), "*.cmd text eol=crlf`n")
        git -C $repo add -A
        git -C $repo -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false commit --quiet --no-gpg-sign -m attrs

        # 前提：git 确实认为文件干净
        git -C $repo status --porcelain | Should -BeNullOrEmpty

        Update-GitWorktreeEol -WorktreePath $repo -Pathspec '*.cmd' | Out-Null

        [System.IO.File]::ReadAllText($file) | Should -Be "@echo off`r`necho hi`r`n"
    }

    It '已是 CRLF 时不重写文件' {
        $file = Join-Path $script:repo 'a.cmd'
        $before = (Get-Item $file).LastWriteTimeUtc
        Start-Sleep -Milliseconds 20

        Update-GitWorktreeEol -WorktreePath $script:repo -Pathspec '*.cmd' | Out-Null

        (Get-Item $file).LastWriteTimeUtc | Should -Be $before
    }

    It '只返回实际被重写的文件' {
        # 只有 a.cmd 被改成 LF，因此它是唯一应出现在结果里的文件
        [System.IO.File]::WriteAllText(
            (Join-Path $script:repo 'a.cmd'), "@echo off`necho hi`n")

        $result = @(Update-GitWorktreeEol -WorktreePath $script:repo -Pathspec '*.cmd', '*.bat')

        $result | Should -HaveCount 1
        $result[0] | Should -Be 'a.cmd'
    }

    It '没有匹配文件时返回空且不报错' {
        $result = @(Update-GitWorktreeEol -WorktreePath $script:repo -Pathspec '*.bat')

        $result | Should -HaveCount 0
    }

    It '路径不是 git 仓库时抛错' {
        $notRepo = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $notRepo | Out-Null

        { Update-GitWorktreeEol -WorktreePath $notRepo -Pathspec '*.cmd' } |
            Should -Throw
    }
}
