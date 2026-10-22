
BeforeAll {
    . "$PSScriptRoot/New-GitWorkspace.ps1"
    $script:OriginalGhHost = $env:GH_HOST
}

AfterAll {
    $env:GH_HOST = $script:OriginalGhHost
}

Describe 'ConvertTo-GitRepoUrl' {
    BeforeEach {
        $env:GH_HOST = $null
        $script:GetLogin = { param($hostName) 'me' }
    }

    It '完整 HTTPS URL 原样返回' {
        ConvertTo-GitRepoUrl -Repository 'https://github.com/foo/bar.git' -GetLogin $script:GetLogin |
            Should -Be 'https://github.com/foo/bar.git'
    }

    It 'HTTP URL 原样返回' {
        ConvertTo-GitRepoUrl -Repository 'http://git.example.com/foo/bar' -GetLogin $script:GetLogin |
            Should -Be 'http://git.example.com/foo/bar'
    }

    It 'OWNER/REPO 补全为 github.com 的 HTTPS URL' {
        ConvertTo-GitRepoUrl -Repository 'foo/bar' -GetLogin $script:GetLogin |
            Should -Be 'https://github.com/foo/bar'
    }

    It '去掉 OWNER/REPO 末尾的 .git' {
        ConvertTo-GitRepoUrl -Repository 'foo/bar.git' -GetLogin $script:GetLogin |
            Should -Be 'https://github.com/foo/bar'
    }

    It '单段 REPO 使用当前登录用户作为 owner' {
        $loginCalls = [System.Collections.Generic.List[string]]::new()
        $getLogin = {
            param($hostName)
            $loginCalls.Add($hostName)
            'me'
        }
        ConvertTo-GitRepoUrl -Repository 'bar' -GetLogin $getLogin |
            Should -Be 'https://github.com/me/bar'
        $loginCalls.Count | Should -Be 1
        $loginCalls[0] | Should -Be 'github.com'
    }

    It 'HOST/OWNER/REPO 使用指定主机' {
        ConvertTo-GitRepoUrl -Repository 'ghe.example.com/foo/bar' -GetLogin $script:GetLogin |
            Should -Be 'https://ghe.example.com/foo/bar'
    }

    It 'GH_HOST 环境变量作为默认主机' {
        $env:GH_HOST = 'ghe.example.com'
        ConvertTo-GitRepoUrl -Repository 'foo/bar' -GetLogin $script:GetLogin |
            Should -Be 'https://ghe.example.com/foo/bar'
    }

    It 'scp 风格 SSH 地址转换为 HTTPS URL' {
        ConvertTo-GitRepoUrl -Repository 'git@github.com:foo/bar.git' -GetLogin $script:GetLogin |
            Should -Be 'https://github.com/foo/bar'
    }

    It '无法确定登录用户时抛错' {
        { ConvertTo-GitRepoUrl -Repository 'bar' -GetLogin { param($h) '' } } |
            Should -Throw
    }

    It 'GetLogin 失败时传播错误' {
        { ConvertTo-GitRepoUrl -Repository 'bar' -GetLogin { param($h) throw 'no login' } } |
            Should -Throw
    }

    It '超过三段的地址抛错' {
        { ConvertTo-GitRepoUrl -Repository 'a/b/c/d' -GetLogin $script:GetLogin } |
            Should -Throw
    }
}
