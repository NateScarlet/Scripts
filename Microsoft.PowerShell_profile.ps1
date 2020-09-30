# https://github.com/PowerShell/PSReadLine/issues/779
Remove-Module -ErrorAction SilentlyContinue PSReadLine

# Refresh env
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Config
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function prompt {
    $p = (Get-Location)
    $p = ($p -replace (":\\Users\\" + [Environment]::UserName), ":\~")
    "PS $p> "
}
