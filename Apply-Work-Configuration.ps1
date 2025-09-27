# spell: words syncthing winget

$(
    "configuration.winget",
    "auto-hotkey.winget"
    "power-toys.winget",
    "work.winget"
) | ForEach-Object {
    winget configure $PSScriptRoot/.config/$_ --accept-configuration-agreements
}
