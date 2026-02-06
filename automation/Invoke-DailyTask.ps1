$ErrorActionPreference="Stop"
# update stretchly stamp without network
if (Test-Path -Path "$env:APPDATA\Stretchly") {
    Get-date -AsUTC  -Format o  |  Out-File -NoNewline "$env:APPDATA\Stretchly\stamp"
    "did update stretchly stamp"

}

$stretchlyExe = "$env:LOCALAPPDATA/Programs/Stretchly/Stretchly.exe"
if (Test-Path $stretchlyExe) {
    $script = "$PSScriptRoot/../specialized/Reset-Stretchly.ps1"
    if (Test-Path $script) {
        Start-Process pwsh -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-File", $script
        "did schedule stretchly reset"
    }
}

& "$PSScriptRoot\Sync-Rime.ps1"
& "$PSScriptRoot\Invoke-AutoGitCommit.ps1"
& "$PSScriptRoot\Delete-Old-Download.ps1"
