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
$proxy = (get-itemproperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings').ProxyServer
if ($proxy) {
    $env:HTTP_PROXY = "http://$proxy"
    $env:HTTPS_PROXY = "http://$proxy"
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
