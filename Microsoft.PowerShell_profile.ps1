# https://github.com/PowerShell/PSReadLine/issues/779
if ((Get-Module -Name PSReadLine).Version.Major -eq 2) {
    Install-Module -Name PSReadLine -RequiredVersion 1.2 -SkipPublisherCheck
    Import-Module -Name PSReadLine
}

# Config
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Refresh env
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# https://bugs.python.org/issue42627
# 获取 Internet 设置的注册表项
$proxySettings = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
# 检查是否启用了代理
if ($proxySettings.ProxyEnable -eq 1) {
    $env:HTTP_PROXY = $proxySettings.ProxyServer
    $env:HTTPS_PROXY = $proxySettings.ProxyServer
    $env:NO_PROXY = "localhost,127.0.0.1,0.0.0.0,$($proxySettings.ProxyOverride -replace ';',',')"
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
