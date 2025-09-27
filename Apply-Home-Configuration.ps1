# spell: words syncthing winget

$(
    "configuration.winget",
    "auto-hotkey.winget"
    "game.winget",
    "syncthing.winget",
    "caddy.winget",
    "power-toys.winget",
    "home.winget"
) | ForEach-Object {
    winget configure $PSScriptRoot/.config/$_ --accept-configuration-agreements
}
