# https://stackoverflow.com/a/11440595
if (-not (
        [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
) {  
    $MyInvocation.MyCommand.Definition
    Start-Process PowerShell -Verb runAs -ArgumentList @(
        "-Version", "3",
        "-NoProfile",
        "& '" + $MyInvocation.MyCommand.Definition + "'"
    )
    return
}

"success"
