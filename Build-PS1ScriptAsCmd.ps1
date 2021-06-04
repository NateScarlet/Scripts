Param (
    [Parameter(
        Mandatory,
        Position = 0,
        HelpMessage = "Script file path"
    )]
    [string]
    $Path,
    [Parameter()]
    [string]
    $LaunchArguments = "-Version 3 -NoProfile -ExecutionPolicy Bypass"
)

# https://stackoverflow.com/a/65314841
$launch_code = @"
@echo off
PowerShell $LaunchArguments -Command "Get-Content '%~dpnx0' -Encoding UTF8 | Select-Object -Skip 5 | Out-String | Invoke-Expression"
IF ERRORLEVEL 1 PAUSE
GOTO :EOF


"@ -replace "`n", "`r`n"

Get-Content $Path | Join-String -Separator "`r`n" -OutputPrefix $launch_code | Set-Content -Encoding UTF8 "$Path.cmd"
