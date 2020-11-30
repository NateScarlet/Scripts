# https://github.com/PowerShell/PSReadLine/issues/779
if ((Get-Module -Name PSReadLine).Version.Major -eq 2) {
    Install-Module -Name PSReadLine -RequiredVersion 1.2 -SkipPublisherCheck
    Import-Module -Name PSReadLine
}

# Refresh env
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Config
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function prompt {
    $p = (Get-Location)
    $p = ($p -replace [regex]::Escape(($env:USERPROFILE -replace '^.+:', ':')), ":\~")
    "PS $p> "
}
