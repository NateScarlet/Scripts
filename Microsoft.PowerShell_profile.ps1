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

function prompt {
    $p = (Get-Location)
    $p = ($p -replace [regex]::Escape(($env:USERPROFILE -replace '^.+:', ':')), ":\~")
    "PS $p> "
}

function New-FileByReplace {
    py $PSScriptRoot/generate-by-replace.py $args
}

Set-Alias "generate:replace" New-FileByReplace
