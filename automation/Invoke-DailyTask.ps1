$ErrorActionPreference="Stop"
# update stretchly stamp without network
if (Test-Path -Path "$env:APPDATA\Stretchly") {
    Get-date -AsUTC  -Format o  |  Out-File -NoNewline "$env:APPDATA\Stretchly\stamp"
    "did update stretchly stamp"
}

& "$PSScriptRoot\Sync-Rime.ps1"
& "$PSScriptRoot\Invoke-AutoGitCommit.ps1"
& "$PSScriptRoot\Delete-Old-Download.ps1"
