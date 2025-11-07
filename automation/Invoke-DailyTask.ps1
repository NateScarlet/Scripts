# update stretchly stamp without network
if (Test-Path -Path "$env:APPDATA\Stretchly") {
    Get-date -AsUTC  -Format o  |  Out-File -NoNewline "$env:APPDATA\Stretchly\stamp"
    "did update stretchly stamp"
}

& "$PSScriptRoot\automation\Sync-Rime.ps1"
& "$PSScriptRoot\automation\Invoke-AutoGitCommit.ps1"
& "$PSScriptRoot\automation\Delete-Old-Download.ps1"
