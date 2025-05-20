# https://github.com/PowerShell/PSReadLine/issues/779
$OutputEncoding = [System.Text.Encoding]::UTF8
[System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[System.Console]::InputEncoding = [System.Text.Encoding]::UTF8

# Refresh env
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# https://bugs.python.org/issue42627
# 获取 Internet 设置的注册表项
$proxySettings = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
# 检查是否启用了代理
if ($proxySettings.ProxyEnable -eq 1) {
    $env:HTTP_PROXY = $proxySettings.ProxyServer
    $env:HTTPS_PROXY = $proxySettings.ProxyServer
    $env:NO_PROXY = "localhost,127.0.0.1,0.0.0.0,$(
        ($proxySettings.ProxyOverride -split ';' | ForEach-Object { $_ `
            -replace '^(\*\.)+','.' `
            -replace '^(\d+)(?:\.\*){1,3}$','$1.0.0.0/8' `
            -replace '^(\d+)\.(\d+)(?:\.\*){1,2}$','$1.$2.0.0/16' `
            -replace '^(\d+)\.(\d+)\.(\d+)\.\*$','$1.$2.$3.0/8' `
        }) -join ',' 
        )"
}

try {
    Import-Module PSReadLine -ErrorAction Stop
}
catch {
    Write-Host "[提示] 命令行增强功能未启用: $_" -ForegroundColor DarkGray
    Write-Host "      运行: Install-Module PSReadLine -Scope CurrentUser" -ForegroundColor Cyan
}


$poshGitAvailable = $false
try {
    Import-Module posh-git -ErrorAction Stop
    $poshGitAvailable = $true
}
catch {
    Write-Host "[提示] Git 状态支持未启用: $_" -ForegroundColor DarkGray
    Write-Host "      运行: Install-Module posh-git -Scope CurrentUser" -ForegroundColor Cyan
}

function global:prompt {
    # 获取当前路径并简化显示 
    # 每个盘符可能都建了个人文件夹　所以要保留盘符显示
    $currentPath = (Get-Location).Path -replace [regex]::Escape(($env:USERPROFILE -replace '^.+:', ':')), ":\~" 
    
    # 添加 Git 状态信息（如果 posh-git 已加载）
    $gitStatus = if ($poshGitAvailable) {
        try {
            # 直接调用 Write-VcsStatus，不依赖 $global:GitStatus
            Write-VcsStatus
        }
        catch {
            "" # 调用失败时返回空字符串
        }
    }
    
    # 组合最终提示
    "PS ${currentPath}${gitStatus}> "
}

function New-FileByReplace {
    py $PSScriptRoot/generate-by-replace.py $args
}

Set-Alias "generate:replace" New-FileByReplace
