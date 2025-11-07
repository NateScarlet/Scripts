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
    $_
    winget configure $PSScriptRoot/.config/$_ --accept-configuration-agreements --proxy=$env:HTTPS_PROXY
}
