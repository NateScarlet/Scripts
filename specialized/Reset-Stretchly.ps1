$ErrorActionPreference = "Stop"

# Use specific path if env var not ready, but user provided logic implies we rely on env vars or standard paths.
# Constructing path dynamically as requested.
$stretchlyExe = "$env:LOCALAPPDATA/Programs/Stretchly/Stretchly.exe"

if (-not (Test-Path $stretchlyExe)) {
    Write-Warning "Stretchly executable not found at: $stretchlyExe"
    exit
}

$now = Get-Date
# Get next exact hour (e.g. 15:00 -> 16:00, 23:59 -> 00:00 next day)
# $now.Date is midnight of current day. $now.Hour is current hour (0-23).
$nextHour = $now.Date.AddHours($now.Hour + 1)
$wait = $nextHour - $now

if ($wait.TotalMilliseconds -gt 0) {
    Write-Host ("Waiting {0:N0} ms until {1} to reset Stretchly..." -f $wait.TotalMilliseconds, $nextHour)
    # Recalculate to minimize drift caused by logging operations
    $msToWait = ($nextHour - (Get-Date)).TotalMilliseconds
    if ($msToWait -gt 0) {
        Start-Sleep -Milliseconds ([int]$msToWait)
    }
}

Write-Host "Executing Stretchly reset..."
& $stretchlyExe reset
