$ErrorActionPreference="Stop"
. "$PSScriptRoot/../lib/Send-Notification.ps1"

# update stretchly stamp without network
try {
    if (Test-Path -Path "$env:APPDATA\Stretchly") {
        Get-date -AsUTC  -Format o  |  Out-File -NoNewline "$env:APPDATA\Stretchly\stamp"
        "did update stretchly stamp"

    }

    & "$PSScriptRoot\Sync-Rime.ps1"
    & "$PSScriptRoot\Invoke-AutoGitCommit.ps1"
    & "$PSScriptRoot\Delete-Old-Download.ps1"
}
catch {
    Write-Warning "执行出错: $_"
    Send-Notification -Title "Invoke-DailyTask 出错" -Message $_.Exception.Message -Priority 8
}
